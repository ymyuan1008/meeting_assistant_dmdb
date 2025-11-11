# 标准库
import os
import re
import uuid
from datetime import datetime, timedelta,timezone
from typing import Optional, Tuple, Dict, Any

# 第三方库
from jose import jwt, JWTError
from loguru import logger
from sqlalchemy.orm import Session

# 自定义模块
from  models import User, UserStatus
from .user_service import UserService


class AuthService(object):
    """JWT认证服务

    功能：
    - 生成、验证、刷新、撤销令牌（黑名单机制）
    - 支持令牌轮换（refresh时旧refresh进入黑名单）
    - 与UserService集成进行用户认证
    - 从环境变量读取配置，记录安全日志
    """

    # 默认配置常量
    DEFAULT_JWT_SECRET: str = "apkMJPa1m693UbMu1PvA1xPi7oExmXoDYqOaCHafMEM"
    DEFAULT_JWT_ALGORITHM: str = "HS256"
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 240  # 4小时
    DEFAULT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30天
    DEFAULT_JWT_ISSUER: str = "meeting-assistant"
    DEFAULT_JWT_AUDIENCE: str = "meeting-assistant-clients"
    # 实例属性
    JWT_SECRET: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    JWT_ISSUER: str
    JWT_AUDIENCE: str
    token_blacklist: set

    def __init__(self) -> None:
        # 环境变量配置
        self.JWT_SECRET = os.getenv("JWT_SECRET", self.DEFAULT_JWT_SECRET)
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", self.DEFAULT_JWT_ALGORITHM)
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(self.DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)))
        self.REFRESH_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(self.DEFAULT_REFRESH_TOKEN_EXPIRE_MINUTES)))
        self.JWT_ISSUER = os.getenv("JWT_ISSUER", self.DEFAULT_JWT_ISSUER)
        self.JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", self.DEFAULT_JWT_AUDIENCE)

        # 强随机密钥保护：若未配置，则生成一次性密钥（生产环境务必配置JWT_SECRET）
        if not self.JWT_SECRET:
            self.JWT_SECRET = uuid.uuid4().hex + uuid.uuid4().hex
            logger.warning("未配置JWT_SECRET，已生成临时密钥。请在生产环境设置JWT_SECRET以确保安全与可持续认证！")

        # 简易黑名单存储（内存）。生产环境可替换为Redis或数据库。
        self.token_blacklist = set()  # 存储被撤销的jti

    # --------------------------- 用户认证 ---------------------------

    async def authenticate_user(self,
                                db: Session,
                                username: str,
                                password: str,
                                user_service: UserService) ->Optional[User]:
        """用户认证：支持邮箱/手机号/用户名登录，校验密码并检查状态"""
        try:
            # 使用UserService的统一登录标识符查找方法
            user: User | None = await user_service.get_user_by_login_identifier(db, identifier=username)

            if not user:
                logger.warning(f"认证失败：用户不存在 username={username}")
                return None
            # 修复 ColumnElement[bool] 类型错误：将比较结果转换为 Python 布尔值
            if str(user.status) != UserStatus.ACTIVE.value:
                logger.warning(f"认证失败：用户状态为{user.status}，拒绝登录 user_id={user.id}")
                return None

            is_valid: bool = user_service.verify_password(user, plain_password=password)
            if not is_valid:
                logger.warning(f"认证失败：密码错误 user_id={user.id}")
                return None

            logger.info(f"认证成功 user_id={user.id} username={username}")
            return user
        except Exception as e:
            logger.error(f"认证过程异常：{e}")
            return None

    # --------------------------- 令牌生成 ---------------------------
    def _build_claims(self,
                      user: User,
                      token_type: str,
                      expires_minutes: int,
                      extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """构建JWT声明
        Args:
            user: 用户对象
            token_type: 令牌类型 (access/refresh)
            expires_minutes: 过期时间（分钟）
            extra: 额外的声明字段
        Returns:
            包含JWT声明的字典
        """
        now = datetime.now(timezone.utc)
        jti = uuid.uuid4().hex
        payload: dict[str, Any] = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.user_role,
            "type": token_type,
            "jti": jti,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
            "iss": self.JWT_ISSUER,
            "aud": self.JWT_AUDIENCE,
        }
        if extra:
            payload.update(extra)
        return payload

    def generate_tokens(self, user: User) -> tuple[str, str]:
        """生成 access_token 与 refresh_token
        Args:
            user: 用户对象
        Returns:
            包含access_token和refresh_token的元组
        Raises:
            JWTError: JWT编码失败时抛出
        """
        try:
            access_payload: dict[str, Any] = self._build_claims(
                user, token_type="access", expires_minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
            refresh_payload: dict[str, Any] = self._build_claims(
                user, token_type="refresh", expires_minutes=self.REFRESH_TOKEN_EXPIRE_MINUTES)

            # 诊断日志：确认 sub 为字符串
            try:
                logger.debug(f"JWT payload types: access.sub={type(access_payload.get('sub'))}, " \
                             f"refresh.sub={type(refresh_payload.get('sub'))}")
            except Exception:
                pass

            access_token = jwt.encode(access_payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
            refresh_token = jwt.encode(refresh_payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

            logger.info(
                f"发放令牌：user_id={user.id} jti_access={access_payload['jti']} jti_refresh={refresh_payload['jti']}")
            return access_token, refresh_token
        except JWTError as e:
            logger.error(f"JWT编码失败: {e}")
            raise
        except Exception as e:
            logger.error(f"生成令牌异常: {e}")
            raise

    # --------------------------- 令牌验证 ---------------------------
    def verify_token(self, token: str, expected_type: str = "access") -> Optional[dict[str, Any]]:
        """验证令牌有效性与类型，并检查黑名单。返回payload或None。
        Args:
            token: JWT令牌字符串
            expected_type: 期望的令牌类型 (access/refresh)
        Returns:
            解码后的令牌载荷字典，验证失败时返回None
        """
        try:
            payload = jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
                audience=self.JWT_AUDIENCE,
                issuer=self.JWT_ISSUER,
            )
            if payload.get("type") != expected_type:
                logger.warning(f"令牌类型不匹配：期待{expected_type}，实际{payload.get('type')}")
                return None

            jti = payload.get("jti")
            if jti in self.token_blacklist:
                logger.warning(f"令牌已被撤销（黑名单）：jti={jti}")
                return None

            return payload
        except JWTError as e:
            logger.warning(f"令牌验证失败：{e}")
            return None
        except Exception as e:
            logger.error(f"令牌验证异常：{e}")
            return None

    # --------------------------- 刷新与轮换 ---------------------------
    def refresh_access_token(self, refresh_token: str, user: User) -> Optional[tuple[str, str]]:
        """使用refresh_token刷新：
        - 验证refresh令牌
        - 令牌轮换：旧refresh加入黑名单，签发新的access与新的refresh
        - 返回 (new_access, new_refresh)
        Args:
            refresh_token: 刷新令牌
            user: 用户对象
        Returns:
            包含新的access_token和refresh_token的元组，刷新失败时返回None
        """
        try:
            payload: Dict[str, Any] | None = self.verify_token(refresh_token, expected_type="refresh")
            if not payload:
                return None

            old_jti = payload.get("jti")
            # 轮换：撤销旧refresh
            self.token_blacklist.add(old_jti)
            logger.info(f"Refresh令牌轮换：撤销旧refresh jti={old_jti} user_id={user.id}")

            # 生成新令牌
            new_access, new_refresh = self.generate_tokens(user)
            return new_access, new_refresh
        except Exception as e:
            logger.error(f"刷新令牌异常: {e}")
            return None

    # --------------------------- 撤销令牌 ---------------------------
    def revoke_token(self, token: str) -> bool:
        """撤销令牌（加入黑名单）。返回是否成功。
        Args:
            token: 要撤销的JWT令牌
        Returns:
            撤销成功返回True，失败返回False
        """
        try:
            payload = jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
                audience=self.JWT_AUDIENCE,
                issuer=self.JWT_ISSUER,
            )
            jti: Any | None = payload.get("jti")
            if not jti:
                logger.warning("撤销失败：令牌不含jti")
                return False
            self.token_blacklist.add(jti)
            logger.info(f"令牌撤销成功 jti={jti} type={payload.get('type')} user_id={payload.get('sub')}")  # type和sub也可能不存在
            return True
        except JWTError as e:
            logger.warning(f"撤销失败：令牌解析错误 {e}")
            return False
        except Exception as e:
            logger.error(f"撤销令牌异常：{e}")
            return False

    # --------------------------- 便捷登录入口 ---------------------------
    async def login_and_issue(self,
                                  db: Session,
                                  username: str,
                                  password: str,
                                  user_service: UserService) -> Optional[tuple[str, str]]:
        """认证用户并签发access/refresh令牌
        Args:
            db: 数据库会话
            username: 用户名/邮箱/手机号
            password: 密码
            user_service: 用户服务实例
        Returns:
            包含access_token和refresh_token的元组，认证失败时返回None
        """
        user: User | None = await self.authenticate_user(db, username, password, user_service)
        if not user:
            return None
        return self.generate_tokens(user)
