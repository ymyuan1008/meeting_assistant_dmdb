from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


# 日常工作报表
class DailyWorkRequest(BaseModel):
    meeting_code: Optional[list[str]] = None
    participants_code: list[str]


class DailyWorkResponse(BaseModel):
    meeting_id: str
    date_time: datetime
    title: str
    agenda: Optional[str] = None
    text_message: Optional[str] = None
    duration_minutes: Optional[int] = None
    participant_names: List[str] = []
    company_names: List[str] = []

    @validator('participant_names', 'company_names', pre=True)
    def split_comma_separated_string(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v

    class Config:
        from_attributes = True


class DailyWorkApiResponse(BaseModel):
    data: list[DailyWorkResponse]
    code: int
    message: str


# 会议台账
class LedgerInfoRequest(BaseModel):
    agenda_id: list[int]


class MeetingLedgerResponse(BaseModel):
    agenda_id: int
    agenda_name: str
    company:  Optional[str] = None
    three_important: str
    topic_type1: str
    topic_type2: str
    topic_type3: str
    is_board_meeting: int
    is_escalation: int
    meeting_time: datetime
    meeting_title: str
    meeting_type: str
    host_user: str
    participant_user: Optional[str]
    planned_attendance: Optional[int]
    actual_attendance: Optional[int]


class LedgerApiResponse(BaseModel):
    data: list[MeetingLedgerResponse]
    code: int
    message: str