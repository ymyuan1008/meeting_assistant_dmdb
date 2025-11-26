
# 标准库
import re
import json
from typing import Union, Dict, Any, List, Optional

# 第三方库
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, Integer, Boolean, func, DateTime
from sqlalchemy.orm import relationship

# 自定义库：导入SQLAlchemy的数据库基类
from models.base import BaseModel as SQLBaseModel  # 重命名SQL基类，明确区分





# SQLAlchemy数据库模型（映射数据库表）
# 继承SQLAlchemy的基类
class Transcription(SQLBaseModel):  # 继承SQL基类
    __tablename__ = "transcriptions"

    id = Column(String(50), primary_key=True, default=SQLBaseModel.generate_uuid)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    speaker_id = Column(String(50), nullable=False)
    speaker_name = Column(String(50))
    text_message = Column(Text, nullable=False)
    created_time = Column(DateTime(timezone=True), nullable=False)
    is_action_item = Column(Boolean, default=False, nullable=True)
    is_decision = Column(Boolean, default=False, nullable=True)

    meeting = relationship("Meeting", back_populates="transcriptions")

    __table_args__ = (
        Index('idx_transcriptions_meeting_id', 'meeting_id'),
        Index('idx_transcriptions_speaker_id', 'speaker_id'),
        Index('idx_transcriptions_created_time', 'created_time'),
    )


class TranscriptionText(SQLBaseModel):  # 继承SQL基类
    __tablename__ = "meeting_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(100), nullable=False, index=True)
    other_meeting_id = Column(String(100), nullable=False)
    speaker_name = Column(String(100), nullable=True)
    text_message = Column(Text, nullable=False)
    created_time = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index('idx_translation_texts_meeting_id', 'meeting_id'),
        Index('idx_translation_texts_other_meeting_id', 'other_meeting_id'),
    )


