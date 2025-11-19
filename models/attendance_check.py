# 第三方库
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Integer

from sqlalchemy.orm import relationship

# 自定义库
from models.base import BaseModel


class Participant(BaseModel):
    __tablename__ = "participants"

    id = Column(String(50), primary_key=True, default=BaseModel.generate_uuid)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    user_code = Column(String(50), ForeignKey("users.id"), nullable=False)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=True)
    user_role = Column(String(50), default="participant")
    is_required = Column(Boolean, nullable=False, default=True)
    attendance_status = Column(String(50), default="pending")  # pending/attended/absent
    created_at = Column(DateTime(timezone=True), default=BaseModel.get_shanghai_time)

    # 关联关系
    user = relationship(
        "User",
        foreign_keys=[user_code],
        back_populates="participations"
    )
    meeting = relationship("Meeting", back_populates="participants")

    __table_args__ = (
        Index('idx_participants_meeting_id', 'meeting_id'),
        Index('idx_participants_user_code', 'user_code'),
        Index('idx_participants_attendance_status', 'attendance_status'),
    )


class PersonSign(BaseModel):
    """人员签到表模型"""
    __tablename__ = "person_sign"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    user_code = Column(String(36), ForeignKey("users.id"), nullable=False)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    # 0=未签到，1=已签到
    is_signed = Column(Integer, default=0)
    # 0=未请假，1=已请假
    is_on_leave = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=BaseModel.get_shanghai_time, comment="创建时间")

    __table_args__ = (
        Index('idx_person_sign_meeting_id', 'meeting_id'),
        Index('idx_person_sign_user_code', 'user_code'),
        Index('idx_person_sign_status', 'is_signed', 'is_on_leave'),
    )
