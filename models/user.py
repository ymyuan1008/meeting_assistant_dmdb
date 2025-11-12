# 标准库
from enum import Enum

# 第三方库
from sqlalchemy import Column, String, Index, ForeignKey,DateTime, text
from sqlalchemy.orm import relationship

# 自定义库
from models.base import BaseModel


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class GenderType(str, Enum):
    """性别类型枚举"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(BaseModel):
    """用户模型 - 管理系统用户信息"""
    __tablename__ = "users"

    # 主键字段
    id = Column(String(36), primary_key=True, default=BaseModel.generate_uuid, comment="用户主键ID（UUID）")
    # 基本信息字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    user_name = Column(String(50), nullable=False, unique=True, comment="用户账号")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号码")
    email = Column(String(255), nullable=True, comment="邮箱地址")
    company = Column(String(200), nullable=True, comment="所属单位名称")

    # 权限和状态字段
    user_role = Column(String(20), nullable=False, default=UserRole.USER.value,
                       comment="用户角色：admin-管理员，user-普通用户")
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value,
                    comment="用户状态：active-激活，inactive-未激活，suspended-暂停")

    # 安全信息字段
    password_hash = Column(String(255), nullable=False, comment="密码哈希值（bcrypt加密）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    # 关联字段
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    created_meetings = relationship("Meeting", foreign_keys="Meeting.created_by", back_populates="creator")
    updated_meetings = relationship("Meeting", foreign_keys="Meeting.updated_by", back_populates="updater")
    participations = relationship("Participant", foreign_keys="Participant.user_code", back_populates="user")

    # 自引用关系
    creator_user = relationship("User", foreign_keys=[created_by], remote_side=[id])
    updater_user = relationship("User", foreign_keys=[updated_by], remote_side=[id])

    # 添加索引
    __table_args__ = (
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'user_role'),
        Index('idx_users_status', 'status')
    )
