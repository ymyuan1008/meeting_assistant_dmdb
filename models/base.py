# 标准库
import uuid
from datetime import datetime
import pytz
from typing import Any

# 第三方库
from sqlalchemy import Column, DateTime, func
from db.databases import Base

# 初始化上海时区
shanghai_tz = pytz.timezone('Asia/Shanghai')

# SQLAlchemy 基础模型
class BaseModel(Base):
    """所有数据库模型的基类，提供公共字段和方法"""
    __abstract__ = True  # 抽象类，不生成实际表

    def __init__(self, **kwargs: Any):
        super().__init__(** kwargs)

    @staticmethod
    def generate_uuid() -> str:
        """生成UUID字符串"""
        return str(uuid.uuid4())

    @staticmethod
    def get_shanghai_time() -> datetime:
        """获取上海时区的当前时间"""
        return datetime.now(shanghai_tz)
