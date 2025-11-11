from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from typing import Dict, Any
from jose import jwt
from datetime import datetime, timedelta, timezone
import os
import time
import re
import hashlib

router = APIRouter(prefix="/api/v1/third-party", tags=["第三方接口"])

# 读取配置（从环境变量）
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")

# JWT 配置，兼容两种命名
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("JWT_SECRET_KEY", ""))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# 令牌过期与时间窗
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("THIRD_PARTY_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
TIMESTAMP_VALID_WINDOW = int(os.getenv("THIRD_PARTY_TIMESTAMP_VALID_WINDOW", "300"))  # 秒


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={
        "code": status_code,
        "message": message,
        "data": None
    })


@router.post("/token", summary="生成第三方访问令牌")
async def generate_third_party_token(token: str = Header(..., alias="token")) -> JSONResponse:
    """根据签名头验证后生成 JWT 令牌

    请求头格式：token: appId-{appId}#timestamp-{timestamp}#sign-{sign}
    验证通过后返回 Bearer Token
    """

    # 解析并验证 token 格式
    pattern = r"appId-(.*?)#timestamp-(\d+)#sign-([a-fA-F0-9]{32})"
    match = re.match(pattern, token)
    if not match:
        return _error(401, "无效的token格式")

    app_id, timestamp_str, sign = match.groups()

    # 验证应用ID
    if not APP_ID or app_id != APP_ID:
        return _error(403, "无效的应用ID")

    # 验证时间窗口（timestamp 为毫秒）
    try:
        timestamp_ms = int(timestamp_str)
    except ValueError:
        return _error(401, "无效的时间戳")

    current_ms = int(time.time() * 1000)
    time_diff_sec = abs(current_ms - timestamp_ms) / 1000.0
    if time_diff_sec > TIMESTAMP_VALID_WINDOW:
        return _error(401, "请求已过期")

    # 验证签名
    sign_str = f"{app_id}{APP_SECRET}{timestamp_ms}"
    expected_sign = hashlib.md5(sign_str.encode()).hexdigest()
    if sign.lower() != expected_sign.lower():
        return _error(401, "无效的签名")

    # 生成 JWT 令牌
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": app_id,
        "type": "third_party",
        "scope": "api",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if not JWT_SECRET:
        # 如果未配置密钥，返回配置错误
        return _error(500, "服务未正确配置JWT密钥")

    access_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "成功",
        "data": {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "scope": "api"
        }
    })