from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator, ConfigDict
from fastapi import UploadFile
import json

from schema.agenda_schema import MeetingAgendaResponse, MeetingAgendaUpdate,MeetingAgendaCreate
from schema.attendance_schema import ParticipantCreate, ParticipantResponse, ParticipantUpdate
from schema.attachment_schema import AttachmentCreate, AttachmentResponse, AttachmentUpdate

# 会议基础信息
class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=75, description="会议标题")
    description: Optional[str] = Field(None, description="会议描述")
    date_time: datetime = Field(..., description="会议时间")
    location: Optional[str] = Field(None, max_length=100, description="会议地点")
    duration_minutes: int = Field(60, ge=1, le=480, description="会议时长（分钟）")


class MeetingCreate(MeetingBase):
    agendas: List["MeetingAgendaCreate"] = []
    participants: List["ParticipantCreate"]
    attachments: List["AttachmentCreate"] = []  # 从文件上传生成


class MeetingUpdate(BaseModel):
    title: str
    description: Optional[str] = None
    date_time: datetime
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    attendance_status: Optional[str] = 'pending'
    agendas: List[MeetingAgendaUpdate] = []
    participants: List["ParticipantUpdate"]
    attachments: Optional[List["AttachmentUpdate"]] = None


class MeetingResponse(MeetingBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    agendas: list["MeetingAgendaResponse"] = []
    participants: list["ParticipantResponse"] = []
    attachments: list["AttachmentResponse"] = []

    class Config(object):
        from_attributes = True


class CreateMeetingRequest(BaseModel):
    """创建会议请求模型（含JSON数据和文件）"""
    meeting_data: str = Field(..., description="会议数据（JSON字符串）")
    files: List[UploadFile] = Field([], description="会议附件（可选）")

    @validator('meeting_data')
    def validate_meeting_data(cls, v):
        if not v:
            raise ValueError("会议数据不能为空")
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("会议数据必须是有效的 JSON 格式")

    def get_meeting_dict(self) -> dict:
        return json.loads(self.meeting_data)


# 会议API响应封装
class MeetingApiResponse(BaseModel):
    data: MeetingResponse
    code: int
    message: str


class MeetingListApiResponse(BaseModel):
    data: List[MeetingResponse]
    code: int
    message: str