from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_HOST: str = Field(default="118.89.93.181", description="数据库主机地址")
    DATABASE_PORT: int = Field(default=5236, description="数据库端口")
    DATABASE_USER: str = Field(default="SYSDBA", description="数据库用户名")
    DATABASE_PASSWORD: str = Field(default="Dameng123", description="数据库密码")
    DATABASE_NAME: str = Field(default="DMDB", description="数据库名称")

    # MinIO配置
    MINIO_ENDPOINT: str = Field(default="118.89.93.181:9000", description="MinIO服务端点")
    MINIO_CONSOLE_ADDRESS: str = Field(default="118.89.93.181:9001", description="MinIO控制台地址")
    MINIO_ACCESS_KEY: str = Field(default="UgQo2VkiIFpP97mW3EKH", description="MinIO访问密钥")
    MINIO_SECRET_KEY: str = Field(default="THPzt62e45seEXtPh65abiZYKqu8tuCLGFDJFEt4", description="MinIO密钥")
    MINIO_SECURE: bool = Field(default=True, description="是否使用HTTPS连接MinIO")

    # CORS配置
    CORS_ORIGINS: list[str] = Field(default=["*"], description="允许的跨域源（用英文逗号分隔多源）")

    # SSL证书配置
    CERT_FILE_PATH: str = Field(default="/home/nebula/ssl_certificate.crt", description="SSL证书路径")
    KEY_FILE_PATH: str = Field(default="/home/nebula/private_key.key", description="SSL密钥路径")

    # 邮件配置
    SMTP_SERVER: str = Field(default="smtp.gmail.com", description="SMTP服务器地址")
    SMTP_PORT: int = Field(default=587, description="SMTP服务器端口")
    EMAIL_USERNAME: Optional[str] = Field(default=None, description="邮件用户名")
    EMAIL_PASSWORD: Optional[str] = Field(default=None, description="邮件密码")
    SENDER_EMAIL: Optional[str] = Field(default=None, description="发件人邮箱")

    # API配置
    API_HOST: str = Field(default="0.0.0.0", description="API服务主机地址")
    API_PORT: int = Field(default=8000, description="API服务端口")

    # 语音识别配置
    SPEECH_RECOGNITION_LANGUAGE: str = Field(default="zh-CN", description="语音识别语言")
    SPEECH_RECOGNITION_TIMEOUT: int = Field(default=5, description="语音识别超时时间（秒）")

    # 文件上传配置
    MAX_UPLOAD_SIZE: str = Field(default="50MB", description="最大上传文件大小")
    UPLOAD_DIRECTORY: str = Field(default="./uploads", description="文件上传目录")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")

    class Config(object):
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def database_url(self) -> str:
        """构建数据库连接URL（达梦数据库）"""
        return f"dm://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


# 全局设置实例
settings = Settings()
