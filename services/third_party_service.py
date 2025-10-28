import hashlib
import time
import httpx
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

class ThirdPartyTokenService:
    def __init__(self):
        # 使用固定的配置值
        self.app_id =  os.getenv("THIRD_PARTY_APP_ID", "tainsureAssistant")
        self.app_secret = os.getenv("THIRD_PARTY_APP_SECRET", "sek9*2JxL8K6p#Lp=ia!-yX@0H0DDoJDDR8d#YGjml!p")
        self.base_url = os.getenv("THIRD_PARTY_BASE_URL", "https://ai.csg.cn/aihear-50-249")
        
        # 保存默认配置（用于可能的覆盖）
        self.default_app_id = self.app_id
        self.default_app_secret = self.app_secret
        self.default_base_url = self.base_url
        
    def _generate_access_token(self, app_id: Optional[str] = None, app_secret: Optional[str] = None) -> str:
        """
        根据文档规范生成access-token
        格式: appId-(appId)#timestamp-(timestamp)#sign-(sign)
        sign计算规则: md5(appId + appsecret + timestamp)
        """
        # 使用传入的参数或默认配置
        current_app_id = app_id or self.default_app_id
        current_app_secret = app_secret or self.default_app_secret
        
        timestamp = str(int(time.time() * 1000))  # 当前时间戳(毫秒)
        
        # 计算签名
        sign_str = f"{current_app_id}{current_app_secret}{timestamp}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        
        # 构造access-token
        access_token = f"appId-{current_app_id}#timestamp-{timestamp}#sign-{sign}"
        return access_token
    
    def _construct_headers(self, app_id: Optional[str] = None, app_secret: Optional[str] = None) -> Dict[str, str]:
        """
        构造请求头
        """
        # 生成 token，并确保 appId 头与 token 中的 appId 一致
        access_token = self._generate_access_token(app_id, app_secret)
        current_app_id = app_id or self.default_app_id
        return {
            "access-token": access_token,
            "appId": current_app_id,
        }
    
    async def get_third_party_token(
        self, 
        base_url: Optional[str] = None, 
        app_id: Optional[str] = None, 
        app_secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        请求第三方接口获取最新token
        
        Args:
            base_url: 第三方服务的基础URL
            app_id: 应用ID
            app_secret: 应用密钥
            
        Returns:
            包含token信息和过期时间的字典
        """
        # 使用传入的参数或默认配置
        self.app_id = app_id or self.default_app_id
        self.app_secret = app_secret or self.default_app_secret
        self.base_url = base_url or self.default_base_url
        
        # 检查基础URL是否已设置，如果未设置则使用默认值，不再报错
        if not self.base_url:
            self.base_url = self.default_base_url
        
        url = f"{self.base_url}/app/open/thridLogin"
        
        headers = self._construct_headers(app_id, app_secret)
        
        try:
            async with httpx.AsyncClient() as client:
                logger.error(f"Requesting third party API: {url}, Headers: {headers}")
                response = await client.post(url, headers=headers, timeout=30)
                # 检查HTTP状态码
                if response.status_code != 200:
                    # 输出响应正文，方便排查 401/403 等问题
                    logger.error(f"Third party API request failed with status code: {response.status_code}, body: {response.text}")
                    return {
                        "code": response.status_code,
                        "msg": f"Third party API request failed: {response.status_code}",
                        "data": "",
                        "map": {}
                    }
                
                # 解析响应
                try:
                    response_data = response.json()
                except Exception:
                    logger.error(f"Third party API returned non-JSON body: {response.text}")
                    return {
                        "code": 500,
                        "msg": "Third party API returned non-JSON body",
                        "data": "",
                        "map": {}
                    }
                
                # 兼容字符串或数字类型的业务 code
                # 兼容字符串或数字类型的业务 code，并统一为整数
                raw_code = response_data.get("code")
                try:
                    business_code = int(str(raw_code))
                except Exception:
                    business_code = 500

                if business_code != 200:
                    logger.error(
                        f"Third party API business error: code={response_data.get('code')}, "
                        f"message={response_data.get('message', 'Unknown error')}"
                    )
                    return {
                        "code": business_code,
                        "msg": response_data.get("message", "Unknown business error"),
                        "data": "",
                        "map": {}
                    }
                
                # 提取token信息
                token = response_data.get("data")
                if not token:
                    logger.error("Token not found in response data")
                    return {
                        "code": 500,
                        "msg": "Token not found in response",
                        "data": "",
                        "map": {}
                    }
                
                # 返回成功结果
                return {
                    "code": 200,
                    "msg": "request success",
                    "data": token,
                    "map": {}
                }
                
        except httpx.TimeoutException:
            logger.error("Third party API request timeout")
            return {
                "code": 408,
                "msg": "Request to third party API timed out",
                "data": "",
                "map": {}
            }
        except httpx.NetworkError:
            logger.error("Network error occurred when requesting third party API")
            return {
                "code": 503,
                "msg": "Network error occurred when requesting third party API",
                "data": "",
                "map": {}
            }
        except Exception as e:
            logger.error(f"Unexpected error when requesting third party API: {str(e)}")
            return {
                "code": 500,
                "msg": f"Unexpected error: {str(e)}",
                "data": "",
                "map": {}
            }

# 创建服务实例
third_party_token_service = ThirdPartyTokenService()