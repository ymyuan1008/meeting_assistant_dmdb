# 标准库

from typing import Any, Optional, Callable, List, Dict


# 第三方库
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

# 自定义模块
from db.dm_conn import get_db
from .auth_service import AuthService
from .user_service import UserService
from  models import User, UserRole, UserStatus

# 单例服务实例（与项目风格保持一致）
auth_service = AuthService()
user_service = UserService()


def _raise_http(status_code: int, message: str, code: str)->None:
    """统一错误响应格式"""
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _extract_bearer_token(authorization: Optional[str]) -> str:
    """从Authorization头中提取Bearer token"""
    if not authorization:
        _raise_http(status.HTTP_401_UNAUTHORIZED, "缺少Authorization头", "unauthorized")
    # 确保authorization不是None后再调用split()
    parts: list[str] = authorization.split()  # type: ignore
    if len(parts) != 2 or parts[0].lower() != "bearer":
        _raise_http(status.HTTP_401_UNAUTHORIZED, "Authorization格式错误，应为'Bearer <token>'", "unauthorized")
    return parts[1]


async def get_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db)
) -> User:
    """依赖函数：从Token中解析并返回当前用户
    - 验证access token
    - 查询用户并检查状态
    - 失败返回401/403
    """
    token = _extract_bearer_token(authorization)

    payload: Dict[str, Any] | None = auth_service.verify_token(token, expected_type="access")
    if not payload:
        _raise_http(status.HTTP_401_UNAUTHORIZED, "无效或过期的Token", "unauthorized")

    user_id = payload.get("sub") if payload else None  # type: ignore
    if not user_id:
        _raise_http(status.HTTP_401_UNAUTHORIZED, "Token缺少用户标识", "unauthorized")

    # 查询用户
    user: Optional[User] = None
    try:
        # 修复：异步方法需要使用 await
        user = await user_service.get_user_by_id(db, user_id)  # type: ignore
    except Exception:
        logger.error("查询当前用户异常", user_id=user_id)
        _raise_http(status.HTTP_401_UNAUTHORIZED, "无法获取当前用户", "unauthorized")

    if not user:
        _raise_http(status.HTTP_401_UNAUTHORIZED, "用户不存在或已被删除", "unauthorized")
    # 修复 ColumnElement[bool] 类型错误：确保 user 不为 None 后再访问属性
    if user.status != UserStatus.ACTIVE.value:  # type: ignore
        _raise_http(status.HTTP_403_FORBIDDEN, f"用户状态为{user.status}，禁止访问", "forbidden")  # type: ignore

    return user


def require_auth(current_user: User = Depends(dependency=get_current_user)) -> User:
    """装饰器/依赖：要求已登录用户"""
    return current_user


def require_admin(current_user: User = Depends(dependency=get_current_user)) -> User:
    """装饰器/依赖：要求管理员权限"""
    # 修复 ColumnElement[bool] 类型错误：将比较结果转换为 Python 布尔值
    if current_user.user_role != UserRole.ADMIN.value:  # type: ignore
        _raise_http(status.HTTP_403_FORBIDDEN, "需要管理员权限", "forbidden")  # type: ignore
    return current_user


def require_roles(roles: list[str]) -> Callable:
    """装饰器工厂：要求特定角色之一
    示例用法：
        @router.get("/path")
        async def handler(current_user: User = Depends(require_roles(["admin", "user"]))):
            ...
    """
    def dependency(current_user: User = Depends(dependency=get_current_user)) -> User:
        # 修复 ColumnElement[bool] 类型错误：将比较结果转换为 Python 布尔值
        if current_user.user_role not in roles:  # type: ignore
            _raise_http(status.HTTP_403_FORBIDDEN, f"需要角色之一: {', '.join(roles)}", "forbidden")  # type: ignore
        return current_user

    return dependency
