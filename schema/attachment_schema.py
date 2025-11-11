from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AttachmentCreate(BaseModel):
    id: str
    meeting_id: str
    file_name: str
    file_path: str
    file_size: int
    content_type: str
    uploaded_by: str
    uploaded_at: datetime


class AttachmentResponse(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_size: int
    content_type: str
    download_url: str

    class Config(object):
        from_attributes = True


class AttachmentUpdate(BaseModel):
    id: Optional[str] = None  # 用于区分新增和更新
    file_name: str
    file_path: str
    file_size: int
    download_url: Optional[str] = None
    content_type: str
    uploaded_by: str