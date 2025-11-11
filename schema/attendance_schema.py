from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, validator


class SignRequest(BaseModel):
    meeting_id: str
    current_users_id: List[str]
# 参会人模型
class ParticipantBase(BaseModel):
    name: str
    user_code: str
    email: Optional[str] = None
    user_role: str = "participant"
    is_required: bool = True
    created_at: datetime


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantUpdate(BaseModel):
    name: Optional[str] = None
    user_code: Optional[str] = None
    email: Optional[str] = None
    user_role: Optional[str] = None
    is_required: Optional[bool] = None


class ParticipantResponse(ParticipantBase):
    id: str
    meeting_id: str
    attendance_status: str

    class Config(object):
        from_attributes = True


# 签到模型
class PersonSignCreate(BaseModel):
    name: str
    user_code: Optional[str] = None
    meeting_id: str
    is_signed: int
    is_on_leave: int


class PersonSignResponse(BaseModel):
    id: int
    name: str
    is_signed: bool
    is_on_leave: bool

    class Config(object):
        from_attributes = True