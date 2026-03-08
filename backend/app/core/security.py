"""安全模块 - JWT / 密码哈希 / 权限控制"""
from __future__ import annotations
import datetime
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database.engine import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + (expires_delta or datetime.timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.security.SECRET_KEY, algorithm=settings.security.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.security.SECRET_KEY, algorithm=settings.security.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.security.SECRET_KEY, algorithms=[settings.security.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI 依赖 - 获取当前登录用户"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")

    from app.database.models import User
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def require_role(*roles: str):
    """角色校验装饰器工厂"""
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user
    return role_checker


def get_current_tenant_id(token_payload: dict) -> Optional[int]:
    """从 token payload 获取租户ID"""
    tenant_id = token_payload.get("tenant_id")
    if tenant_id and tenant_id != "":
        try:
            return int(tenant_id)
        except (ValueError, TypeError):
            return None
    return None


def require_tenant(tenant_id: int):
    """租户校验装饰器工厂 - 确保用户属于指定租户"""
    async def tenant_checker(current_user=Depends(get_current_user)):
        # 管理员可以访问所有租户
        if current_user.role == "admin":
            return current_user
        
        # 非管理员必须属于指定租户
        if current_user.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此租户数据")
        return current_user
    return tenant_checker


def require_tenant_or_admin():
    """租户或管理员校验"""
    async def checker(current_user=Depends(get_current_user)):
        # 管理员可以访问所有
        if current_user.role == "admin":
            return current_user
        
        # 其他角色必须有租户
        if not current_user.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要租户权限")
        return current_user
    return checker
