# 从各模块导入模型，统一对外导出
from .base import Base
from .agenda import Agendas
from .attachment import Attachment
from .attendance_check import Participant, PersonSign
from .content import Transcription, TranscriptionText
from .meeting import Meeting
from .message import Message, MessageRecipient
from .user import User, UserRole, UserStatus, GenderType

# 可选：通过 __all__ 明确对外暴露的模型，便于外部以 `from models import X` 导入
__all__ = [
    "Base",
    "Agendas",
    "Attachment",
    "Participant",
    "PersonSign",
    "Transcription",
    "TranscriptionText",
    "Meeting",
    "Message",
    "MessageRecipient",
    "User",
    "UserRole",
    "UserStatus",
    "GenderType"
]