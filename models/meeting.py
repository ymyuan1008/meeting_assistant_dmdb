# 第三方库
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

# 自定义库
from models.base import BaseModel


class Meeting(BaseModel):
    __tablename__ = "meetings"

    id = Column(String(50), primary_key=True, default=BaseModel.generate_uuid)
    title = Column(String(75), nullable=False)
    description = Column(Text, nullable=True)
    date_time = Column(DateTime, nullable=False)
    location = Column(String(100))
    duration_minutes = Column(Integer, default=60)
    # 状态：scheduled(已排期), in_progress(进行中), completed(已完成), cancelled(已取消)
    status = Column(String(50), default="scheduled")
    created_at = Column(DateTime(timezone=True), default=BaseModel.get_shanghai_time)
    updated_at = Column(DateTime(timezone=True), default=BaseModel.get_shanghai_time,
                        onupdate=BaseModel.get_shanghai_time)

    # 关联字段：创建者/更新者
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="meeting")
    agendas = relationship("Agendas", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")

    # 创建者/更新者反向关系
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_meetings")
    updater = relationship("User", foreign_keys=[updated_by], back_populates="updated_meetings")

    __table_args__ = (
        Index('idx_meetings_status', 'status'),
        Index('idx_meetings_date_time', 'date_time'),
    )
