# 第三方库
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

# 自定义库
from models.base import BaseModel


class Attachment(BaseModel):
    __tablename__ = "attachments"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id"))
    file_name = Column(String)
    file_path = Column(String)
    download_url = Column(String)
    file_size = Column(Integer)
    content_type = Column(String)
    uploaded_by = Column(String)
    uploaded_at = Column(DateTime)

    # 关联关系
    meeting = relationship("Meeting", back_populates="attachments")

    __table_args__ = (
        Index('idx_attachments_meeting_id', 'meeting_id'),
        Index('idx_attachments_uploaded_by', 'uploaded_by'),
    )