from fastapi import APIRouter, Depends,  Query
from services.third_party_service import third_party_token_service
from typing import Dict, Any, Optional
from services.auth_dependencies import require_auth
router = APIRouter(prefix="/api/third-party", tags=["第三方接口"])

@router.get("/token", summary="获取第三方访问令牌")
async def get_third_party_token(
    base_url: Optional[str] = Query(None, description="第三方服务的基础URL"),
    app_id: Optional[str] = Query(None, description="第三方服务的应用ID"),
    app_secret: Optional[str] = Query(None, description="第三方服务的应用密钥"),
    _ = Depends(require_auth)
) -> dict[str, Any]:
    """
    请求第三方接口获取最新访问令牌

    Args:
        base_url: 第三方服务的基础URL
        app_id: 第三方服务的应用ID
        app_secret: 第三方服务的应用密钥

    Returns:
        包含token信息的响应
    """
    result = await third_party_token_service.get_third_party_token(base_url, app_id, app_secret)

    # 直接返回第三方服务的结果，格式已符合要求
    return result
