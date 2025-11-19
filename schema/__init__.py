# 从各模块导入模型，统一对外导出
from .agenda_schema import (
    ThreeImportantEnum,
    MeetingAgendaBase,
    MeetingAgendaCreate,
    MeetingAgendaUpdate,
    MeetingAgendaResponse
)
from .attachment_schema import (
    AttachmentCreate,
    AttachmentResponse,
    AttachmentUpdate
)
from .attendance_schema import (
    SignRequest,
    ParticipantBase,
    ParticipantCreate,
    ParticipantUpdate,
    ParticipantResponse,
    PersonSignCreate,
    PersonSignResponse
)
from .content_schema import (
    TranscriptionBase,
    TranscriptionCreate,
     TranslationTextRequest,
    TranscriptionResponse,
    TranscriptionTextResponse,
    WebSocketMessage,
    TranslationItem,
    TranslationBatch
)
from .meeting_schema import (
    MeetingBase,
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    CreateMeetingRequest,
    MeetingApiResponse,
    MeetingListApiResponse
)
from .message_schema import (
    MessageCreate,
    MessageRecipientResponse,
    MessageResponse,
    BatchMarkReadRequest,
    MessageForUserResponse
)
from .report_schema import (
    DailyWorkRequest,
    DailyWorkResponse,
    DailyWorkApiResponse,
    LedgerInfoRequest,
    MeetingLedgerResponse,
    LedgerApiResponse
)
from .user_schema import (
    UserBase,
    UserResponse,
    UserBasicResponse,
    UserRegister,
    UserLogin,
    UserCreate,
    UserUpdate,
    PasswordChange
)

# 可选：导出所有模型到包的根命名空间，方便外部以 `from schema import X` 导入
__all__ = [
    # 议程相关
    "ThreeImportantEnum",
    "MeetingAgendaBase",
    "MeetingAgendaCreate",
    "MeetingAgendaUpdate",
    "MeetingAgendaResponse",
    # 附件相关
    "AttachmentCreate",
    "AttachmentResponse",
    "AttachmentUpdate",
    # 参会与签到相关
    "SignRequest",
    "ParticipantBase",
    "ParticipantCreate",
    "ParticipantUpdate",
    "ParticipantResponse",
    "PersonSignCreate",
    "PersonSignResponse",
    # 内容处理相关
    "TranscriptionBase",
    "TranscriptionCreate",
    "TranscriptionResponse",
    "WebSocketMessage",
    "TranslationItem",
    "TranslationBatch",
    # 会议基础相关
    "MeetingBase",
    "MeetingCreate",
    "MeetingUpdate",
    "MeetingResponse",
    "CreateMeetingRequest",
    "MeetingApiResponse",
    "MeetingListApiResponse",
    # 消息相关
    "MessageCreate",
    "MessageRecipientResponse",
    "MessageResponse",
    "BatchMarkReadRequest",
    "MessageForUserResponse",
    # 报表相关
    "DailyWorkRequest",
    "DailyWorkResponse",
    "DailyWorkApiResponse",
    "LedgerInfoRequest",
    "MeetingLedgerResponse",
    "LedgerApiResponse",
    # 用户相关
    "UserBase",
    "UserResponse",
    "UserBasicResponse",
    "UserRegister",
    "UserLogin",
    "UserCreate",
    "UserUpdate",
    "PasswordChange"
]