from pydantic_settings import BaseSettings
from pydantic import Field  # 用于设置默认值或描述


class Settings(BaseSettings):
    # 1. 补充你在环境变量中配置的所有字段（按实际类型定义）
    # 数据库配置
    DATABASE_HOST: str = Field(default="118.89.93.181", description="达梦数据库主机地址")
    DATABASE_PORT: int = Field(default=5236, description="达梦数据库端口")
    DATABASE_NAME: str = Field(default="DMSERVER", description="数据库名称")
    DATABASE_USER: str = Field(default="SYSDBA", description="数据库用户名")
    DATABASE_PASSWORD: str = Field(default="Dameng123", description="数据库密码")

    # SSL证书相关
    CERT_FILE_PATH: str = Field(..., description="SSL证书文件路径")
    KEY_FILE_PATH: str = Field(..., description="私钥文件路径")


    # SMTP邮件相关
    SMTP_SERVER: str = Field(..., description="SMTP服务器地址")
    SMTP_PORT: int = Field(587, description="SMTP服务器端口，默认587")

    # API服务相关
    API_HOST: str = Field("0.0.0.0", description="API服务绑定的主机，默认0.0.0.0")
    API_PORT: int = Field(8000, description="API服务端口，默认8000")

    # 语音识别相关
    SPEECH_RECOGNITION_LANGUAGE: str = Field("zh-CN", description="语音识别语言，默认中文")
    SPEECH_RECOGNITION_TIMEOUT: int = Field(5, description="语音识别超时时间（秒），默认5")

    # 文件上传相关
    MAX_UPLOAD_SIZE: str = Field("50MB", description="最大上传文件大小，默认50MB")
    UPLOAD_DIRECTORY: str = Field("./uploads", description="文件上传目录，默认./uploads")

    # 日志相关
    LOG_LEVEL: str = Field("INFO", description="日志级别，默认INFO")

    # 之前的CORS_ORIGINS字段（已正确定义的保留）
    CORS_ORIGINS: list[str] = Field(["http://localhost:3000"], description="跨域允许的源")

    class Config(object):
        env_file = ".env"  # 确保读取.env文件（若用环境变量则无需此配置）
        case_sensitive = True  # 字段名大小写敏感（如MYSQL_HOST≠mysql_host）



    @property
    def database_url(self) -> str:
        """构建达梦数据库连接URL"""
        return f"dm://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}" \
               f":{self.DATABASE_PORT}/{self.DATABASE_NAME}"


# 全局设置实例
settings = Settings()
