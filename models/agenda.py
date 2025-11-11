# 第三方库
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Index
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import relationship

# 自定义库
from models.base import BaseModel


class Agendas(BaseModel):
    __tablename__ = "agendas"

    agenda_id = Column(Integer, primary_key=True, autoincrement=True, comment="议程ID")
    agenda_name = Column(String(255), nullable=False, comment="议程名称")
    meeting_form = Column(String(100), nullable=True, comment="会议形式")
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    is_board_meeting = Column(TINYINT(1), nullable=False, default=0, comment="是否董事会（0=否，1=是）")
    three_important = Column(String(100), nullable=True, comment="三重一大分类")
    topic_type1 = Column(String(100), nullable=True, comment="议题类型1")
    topic_type2 = Column(String(100), nullable=True, comment="议题类型2")
    topic_type3 = Column(String(100), nullable=True, comment="议题类型3")
    is_escalation = Column(TINYINT(1), nullable=False, default=0, comment="是否上会（0=否，1=是）")
    create_time = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(String(50), nullable=True, comment="创建人用户ID")

    # 关联关系
    meeting = relationship("Meeting", back_populates="agendas")

    __table_args__ = (
        Index('idx_agendas_meeting_id', 'meeting_id'),
        Index('idx_agendas_three_important', 'three_important'),
    )