"""用户管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.engine import get_db
from app.database.models import User, OperationLog
from app.core.security import get_current_user, decode_token, create_access_token
from app.services.user_service import UserService
from app.schemas.user import (
    UserCreate, LoginRequest, TokenResponse, UserResponse, 
    PasswordChangeRequest, UserUpdateRequest, RefreshTokenRequest
)
from app.core.logging_config import get_logger
import ipaddress

logger = get_logger(__name__)
router = APIRouter()

# 注册白名单（可配置允许注册的 IP 或关闭注册）
ALLOW_REGISTRATION = False  # 生产环境建议关闭
REGISTRATION_SECRET = ""  # 可选：注册密钥


@router.post("/register", summary="注册用户")
async def register(data: UserCreate, db: AsyncSession = Depends(get_db), request=None):
    if not ALLOW_REGISTRATION:
        raise HTTPException(403, "当前不允许自行注册，请联系管理员")
    
    if REGISTRATION_SECRET and data.password != REGISTRATION_SECRET:
        raise HTTPException(403, "注册密钥无效")
    
    if not UserService.validate_password_strength(data.password):
        raise HTTPException(400, "密码强度不足，需包含：大小写字母、数字、特殊字符，长度至少8位")
    
    try:
        user = await UserService.create_user(
            data.username, data.password, db, data.role or "examiner",
            email=data.email, full_name=data.full_name, department=data.department
        )
        
        await OperationLog.log(
            db, user_id=user.id, operation_type="user_register",
            operation_target=f"user:{user.username}",
            result="success"
        )
        
        return {"code": 200, "message": "注册成功", "data": UserResponse.model_validate(user).model_dump()}
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(400, f"注册失败: {str(e)}")


@router.post("/login", summary="用户登录")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db), request=None):
    # 记录登录尝试
    client_ip = request.client.host if request else "unknown"
    
    result = await UserService.authenticate(data.username, data.password, db)
    if not result:
        await OperationLog.log(
            db, operation_type="user_login_failed",
            operation_target=f"username:{data.username}",
            ip_address=client_ip,
            result="failed",
            error_message="用户名或密码错误"
        )
        raise HTTPException(401, "用户名或密码错误")
    
    user = result["user"]
    
    await OperationLog.log(
        db, user_id=user["id"], operation_type="user_login",
        operation_target=f"user:{user['username']}",
        ip_address=client_ip,
        result="success"
    )
    
    return {"code": 200, "data": result}


@router.post("/refresh", summary="刷新令牌")
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "无效的刷新令牌")
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "无效的令牌")
        
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(401, "用户不存在或已禁用")
        
        access_token = create_access_token({"sub": str(user.id), "role": user.role})
        
        return {
            "code": 200, 
            "data": {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    except Exception as e:
        logger.error(f"刷新令牌失败: {e}")
        raise HTTPException(401, "令牌刷新失败")


@router.post("/logout", summary="用户登出")
async def logout(db: AsyncSession = Depends(get_db), user=Depends(get_current_user), request=None):
    client_ip = request.client.host if request else "unknown"
    
    await OperationLog.log(
        db, user_id=user.id, operation_type="user_logout",
        operation_target=f"user:{user.username}",
        ip_address=client_ip,
        result="success"
    )
    
    return {"code": 200, "message": "登出成功"}


@router.get("/me", summary="获取当前用户")
async def get_me(user=Depends(get_current_user)):
    return {"code": 200, "data": UserResponse.model_validate(user).model_dump()}


@router.put("/me", summary="更新个人信息")
async def update_me(
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """用户更新自己的个人信息（姓名、邮箱、部门）"""
    target_user = await UserService.get_user(user.id, db)
    if not target_user:
        raise HTTPException(404, "用户不存在")
    
    # 只允许更新部分字段（不允许修改用户名、角色、激活状态）
    if data.full_name is not None:
        target_user.full_name = data.full_name
    if data.email is not None:
        target_user.email = data.email
    if data.department is not None:
        target_user.department = data.department
    
    await db.flush()
    
    return {"code": 200, "message": "更新成功", "data": UserResponse.model_validate(target_user).model_dump()}


@router.post("/me/password", summary="修改密码")
async def change_pw(data: PasswordChangeRequest, db: AsyncSession = Depends(get_db), 
                    user=Depends(get_current_user), request=None):
    if not UserService.validate_password_strength(data.new_password):
        raise HTTPException(400, "密码强度不足")
    
    ok = await UserService.change_password(user.id, data.old_password, data.new_password, db)
    if not ok:
        await OperationLog.log(
            db, user_id=user.id, operation_type="password_change_failed",
            operation_target=f"user:{user.username}",
            result="failed",
            error_message="原密码错误"
        )
        raise HTTPException(400, "原密码错误")
    
    await OperationLog.log(
        db, user_id=user.id, operation_type="password_change",
        operation_target=f"user:{user.username}",
        result="success"
    )
    
    return {"code": 200, "message": "密码修改成功"}


# ─── 管理员接口 ─────────────────────────────────────────────
# 注意：具体路径必须在带参数路径之前定义

@router.post("/", summary="创建用户")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    # 检查用户名是否已存在
    existing = await UserService.get_user_by_username(data.username, db)
    if existing:
        raise HTTPException(400, "用户名已存在")
    
    # 验证密码强度
    if not UserService.validate_password_strength(data.password):
        raise HTTPException(400, "密码强度不足，需包含：大小写字母、数字、特殊字符，长度至少8位")
    
    try:
        new_user = await UserService.create_user(
            data.username,
            data.password,
            db,
            role=data.role or "examiner",
            email=data.email,
            full_name=data.full_name,
            department=data.department
        )
        
        await OperationLog.log(
            db, user_id=user.id, operation_type="user_create",
            operation_target=f"user:{new_user.username}",
            operation_details={"role": new_user.role},
            result="success"
        )
        
        return {"code": 200, "message": "创建成功", "data": UserResponse.model_validate(new_user).model_dump()}
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        raise HTTPException(400, f"创建失败: {str(e)}")


@router.get("/", summary="获取用户列表")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if keyword:
        like = f"%{keyword}%"
        filt = (User.username.like(like) | User.full_name.like(like) | User.email.like(like))
        query = query.where(filt)
        count_query = count_query.where(filt)
    
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(User.created_at.desc()).offset((page-1)*page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    
    return {
        "code": 200,
        "data": {
            "items": [UserResponse.model_validate(u).model_dump() for u in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(404, "用户不存在")
    
    return {"code": 200, "data": UserResponse.model_validate(target_user).model_dump()}


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int, 
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    target_user = await UserService.get_user(user_id, db)
    if not target_user:
        raise HTTPException(404, "用户不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        if not UserService.validate_password_strength(update_data["password"]):
            raise HTTPException(400, "密码强度不足")
        update_data["password_hash"] = UserService.hash_password(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(target_user, key, value)
    
    await db.flush()
    
    await OperationLog.log(
        db, user_id=user.id, operation_type="user_update",
        operation_target=f"user:{target_user.username}",
        operation_details={"updated_fields": list(update_data.keys())},
        result="success"
    )
    
    return {"code": 200, "message": "更新成功", "data": UserResponse.model_validate(target_user).model_dump()}


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    if user_id == user.id:
        raise HTTPException(400, "不能删除自己的账号")
    
    target_user = await UserService.get_user(user_id, db)
    if not target_user:
        raise HTTPException(404, "用户不存在")
    
    username = target_user.username
    await db.delete(target_user)
    
    await OperationLog.log(
        db, user_id=user.id, operation_type="user_delete",
        operation_target=f"user:{username}",
        result="success"
    )
    
    return {"code": 200, "message": "删除成功"}


@router.post("/{user_id}/toggle-active", summary="启用/禁用用户")
async def toggle_user_active(user_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ["admin"]:
        raise HTTPException(403, "权限不足")
    
    target_user = await UserService.get_user(user_id, db)
    if not target_user:
        raise HTTPException(404, "用户不存在")
    
    if user_id == user.id:
        raise HTTPException(400, "不能禁用自己的账号")
    
    target_user.is_active = not target_user.is_active
    await db.flush()
    
    action = "启用" if target_user.is_active else "禁用"
    await OperationLog.log(
        db, user_id=user.id, operation_type=f"user_{'enable' if target_user.is_active else 'disable'}",
        operation_target=f"user:{target_user.username}",
        result="success"
    )
    
    return {"code": 200, "message": f"{action}成功", "data": {"is_active": target_user.is_active}}
