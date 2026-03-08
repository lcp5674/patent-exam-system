"""用户管理服务"""
from __future__ import annotations
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import User
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from app.config import settings


class UserService:

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """验证密码强度：至少8位，包含大小写字母、数字和特殊字符"""
        if len(password) < 8:
            return False
        if not re.search(r"[A-Z]", password):
            return False
        if not re.search(r"[a-z]", password):
            return False
        if not re.search(r"[0-9]", password):
            return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False
        return True

    @staticmethod
    def hash_password(password: str) -> str:
        return get_password_hash(password)

    @staticmethod
    async def create_user(username: str, password: str, db: AsyncSession, role: str = "examiner", **kwargs) -> User:
        user = User(username=username, password_hash=get_password_hash(password), role=role, **kwargs)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(username: str, password: str, db: AsyncSession) -> dict | None:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        access_token = create_access_token({"sub": str(user.id), "role": user.role, "tenant_id": str(user.tenant_id) if user.tenant_id else ""})
        refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role})
        return {
            "access_token": access_token, "refresh_token": refresh_token,
            "token_type": "bearer", "expires_in": settings.security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id, 
                "username": user.username, 
                "role": user.role, 
                "full_name": user.full_name,
                "tenant_id": user.tenant_id,
            },
        }

    @staticmethod
    async def get_user(user_id: int, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(username: str, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def change_password(user_id: int, old_password: str, new_password: str, db: AsyncSession) -> bool:
        user = await UserService.get_user(user_id, db)
        if not user or not verify_password(old_password, user.password_hash):
            return False
        user.password_hash = get_password_hash(new_password)
        await db.flush()
        return True
