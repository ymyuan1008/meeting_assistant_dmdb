from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    title: str
    content: str
    recipient_ids: list[str]  # 接收者ID列表


class MessageRecipientResponse(BaseModel):
    recipient_id: str
    is_read: bool
    read_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    id: int
    title: str
    content: str
    sender_id: str
    created_at: datetime
    recipients: list[MessageRecipientResponse] = []

    class Config(object):
        from_attributes = True


class BatchMarkReadRequest(BaseModel):
    message_ids: list[int]


class MessageForUserResponse(BaseModel):
    id: int
    title: str
    content: str
    sender_id: str
    created_at: datetime
    recipient_id: str
    is_read: bool
    read_at: Optional[datetime] = None

    class Config(object):
        from_attributes = True