from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ThreeImportantEnum(str, Enum):
    """三重一大分类枚举"""
    MAJOR_DECISION = "重大决策事项"
    MAJOR_PROJECT = "重大项目安排"
    LARGE_FUND_OPERATION = "大额度资金运作事项"
    IMPORTANT_PERSONNEL = "重要人事任免事项"
    NON_THREE_IMPORTANT = "非三重一大事项"


class MeetingAgendaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agenda_name: str = Field(..., min_length=1, max_length=255, description="议程名称")
    meeting_form: Optional[str] = Field(None, max_length=100, description="会议形式")
    is_board_meeting: bool = Field(False, description="是否董事会")
    three_important: Optional[str]  = Field(None, description="三重一大分类")
    topic_type1: Optional[str] = Field(None, max_length=100, description="议题类型1")
    topic_type2: Optional[str] = Field(None, max_length=100, description="议题类型2")
    topic_type3: Optional[str] = Field(None, max_length=100, description="议题类型3")
    is_escalation: bool = Field(False, description="是否上会")
    created_by: Optional[str] = Field(None, max_length=50, description="创建人用户ID")


class MeetingAgendaCreate(MeetingAgendaBase):
    pass


class MeetingAgendaUpdate(BaseModel):
    """更新议程的模型（所有字段可选）"""
    model_config = ConfigDict(from_attributes=True)

    agenda_name: Optional[str] = Field(None, min_length=1, max_length=255, description="议程名称")
    meeting_form: Optional[str] = Field(None, max_length=100, description="会议形式")
    is_board_meeting: Optional[bool] = Field(None, description="是否董事会")
    three_important: Optional[str] = Field(None, description="三重一大分类")
    topic_type1: Optional[str] = Field(None, max_length=100, description="议题类型1")
    topic_type2: Optional[str] = Field(None, max_length=100, description="议题类型2")
    topic_type3: Optional[str] = Field(None, max_length=100, description="议题类型3")
    is_escalation: Optional[bool] = Field(None, description="是否上会")
    created_by: Optional[str] = Field(None, max_length=50, description="创建人用户ID")


class MeetingAgendaResponse(MeetingAgendaBase):
    """议程响应模型（含数据库生成字段）"""
    agenda_id: int = Field(..., description="议程ID")
    meeting_id: str = Field(..., description="关联会议ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")