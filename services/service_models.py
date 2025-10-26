# 标准库
import uuid
from datetime import datetime
from enum import Enum
import pytz
from typing import Union, Dict, Any, List
import json
import re

from pydantic import BaseModel,validator, Field
from typing import Optional, Tuple, Dict, Any



shanghai_tz = pytz.timezone('Asia/Shanghai')
from pydantic import BaseModel, Field, validator
# 第三方库 - SQLAlchemy相关
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    func,
    UniqueConstraint
)
from sqlalchemy import (
     BigInteger,
    Text,
    Integer,
    Boolean
)
from sqlalchemy.orm import relationship
# 自定义库
from db.databases import Base


class SentenceItem(BaseModel):
    sentence: str
    progressive: str = ""

    @property
    def cleaned_sentence(self) -> str:
        """清理后的句子内容，移除说话人标记"""
        # 移除说话人标记模式：👤 说话人X:
        cleaned = re.sub(r'^\\n👤\s*说话人[A-Z]:\s*["\']?', '', self.sentence)
        cleaned = re.sub(r'["\']?$', '', cleaned)
        return cleaned.strip()

    @property
    def speaker(self) -> Optional[str]:
        """提取说话人信息"""
        match = re.search(r'👤\s*(说话人[A-Z])', self.sentence)
        return match.group(1) if match else None

    @property
    def has_content(self) -> bool:
        """判断句子是否有实际内容"""
        return bool(self.cleaned_sentence)


class TranslateTextContent(BaseModel):
    completedSentences: List[SentenceItem] = Field(default_factory=list)
    textVal: str = ""

    @property
    def valid_sentences(self) -> List[SentenceItem]:
        """获取有实际内容的句子"""
        return [item for item in self.completedSentences if item.has_content]

    @property
    def speakers(self) -> List[str]:
        """获取所有说话人列表（去重）"""
        speaker_list = [item.speaker for item in self.valid_sentences if item.speaker]
        return list(dict.fromkeys(speaker_list))  # 保持顺序去重

    @property
    def all_text(self) -> str:
        """获取所有有效句子的合并文本"""
        return ' '.join([item.cleaned_sentence for item in self.valid_sentences])

    def get_sentences_by_speaker(self, speaker: str) -> List[str]:
        """获取指定说话人的所有句子"""
        return [
            item.cleaned_sentence
            for item in self.valid_sentences
            if item.speaker == speaker
        ]


class TranslationTextRequest(BaseModel):
    meetingId: str
    translateText: Union[str, Dict[str, Any], TranslateTextContent]
    speakerName: str = Field(default="")

    @validator('translateText', pre=True)
    def parse_translate_text(cls, v):
        """将字符串类型的translateText解析为字典"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v  # 如果解析失败，返回原字符串
        return v

    def get_parsed_translate_text(self) -> TranslateTextContent:
        """获取解析后的translateText内容"""
        if isinstance(self.translateText, str):
            try:
                parsed = json.loads(self.translateText)
            except json.JSONDecodeError:
                # 如果解析失败，返回空的TranslateTextContent
                return TranslateTextContent()
        else:
            parsed = self.translateText

        # 转换为强类型模型
        return TranslateTextContent(**parsed)

    def extract_conversation_data(self) -> Dict[str, Any]:
        """提取完整的对话数据"""
        content = self.get_parsed_translate_text()

        # 按说话人分组
        conversation_by_speaker = {}
        for speaker in content.speakers:
            conversation_by_speaker[speaker] = content.get_sentences_by_speaker(speaker)

        return {
            "meeting_id": self.meetingId,
            "speaker_name": self.speakerName,
            "speakers": content.speakers,
            "total_sentences": len(content.completedSentences),
            "valid_sentences": len(content.valid_sentences),
            "conversation_by_speaker": conversation_by_speaker,
            "full_text": content.all_text,
            "sentences_detail": [
                {
                    "original": item.sentence,
                    "cleaned": item.cleaned_sentence,
                    "speaker": item.speaker,
                    "has_content": item.has_content,
                    "progressive": item.progressive
                }
                for item in content.completedSentences
            ]
        }


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class TranslationText(Base):
    __tablename__ = "translation_texts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(100), nullable=False, index=True)
    speaker_name = Column(String(100), nullable=True)  # 如果没有说话人信息可以设为可选
    text = Column(Text, nullable=False)  # 使用Text类型存储长文本
    created_time = Column(DateTime, default=datetime.utcnow)

class GenderType(str, Enum):
    """性别类型枚举"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(Base):
    """用户模型 - 管理系统用户信息"""
    __tablename__ = "users"

    # 主键字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="用户主键ID（UUID）")
    # 基本信息字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    user_name = Column(String(50), nullable=False, unique=True, comment="用户账号")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号码")
    email = Column(String(255), nullable=True, unique=True, comment="邮箱地址")
    company = Column(String(200), nullable=True, comment="所属单位名称")

    # 权限和状态字段
    user_role = Column(String(20), nullable=False, default=UserRole.USER.value,
                       comment="用户角色：admin-管理员，user-普通用户")
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value,
                    comment="用户状态：active-激活，inactive-未激活，suspended-暂停")

    # 安全信息字段
    password_hash = Column(String(255), nullable=False, comment="密码哈希值（bcrypt加密）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="更新时间")

    # 关联字段
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    created_meetings = relationship("Meeting", foreign_keys="Meeting.created_by", back_populates="creator")
    updated_meetings = relationship("Meeting", foreign_keys="Meeting.updated_by", back_populates="updater")
    participations = relationship("Participant", foreign_keys="Participant.user_code", back_populates="user")


    # 自引用关系
    creator_user = relationship("User", foreign_keys=[created_by], remote_side=[id])
    updater_user = relationship("User", foreign_keys=[updated_by], remote_side=[id])

    # 添加索引
    __table_args__ = (
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'user_role'),
        Index('idx_users_status', 'status')
    )

# 定义人员签到表模型
class PersonSign(Base):
    __tablename__ = "person_sign"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    user_code = Column(String(36), ForeignKey("users.id"), nullable=False)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    is_signed = Column(Boolean, default=False)
    is_on_leave = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="创建时间")

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(75), nullable=False)
    description = Column(Text)
    date_time = Column(DateTime, nullable=False)
    location = Column(String(100))
    duration_minutes = Column(Integer, default=60)
    agenda = Column(Text)
    # scheduled, in_progress, completed, cancelled
    status = Column(String(50), default="scheduled")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), onupdate=datetime.utcnow)
    # 关联字段：创建者/更新者
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")

    # 创建者/更新者反向关系
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_meetings")
    updater = relationship("User", foreign_keys=[updated_by], back_populates="updated_meetings")


class Participant(Base):
    __tablename__ = "participants"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    user_code = Column(String(50), ForeignKey("users.id"), nullable=False)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    user_role = Column(String(50), default="participant")
    is_required = Column(Boolean, default=True)
    attendance_status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz))

    # 与 User 模型中的 participations 对应
    user = relationship(
        "User",
        foreign_keys=[user_code],
        back_populates="participations"
    )
    meeting = relationship("Meeting", back_populates="participants")


class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    speaker_id = Column(String(50), nullable=False)
    speaker_name = Column(String(50))
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.utcnow(), nullable=False)
    confidence_score = Column(Integer, default=100)
    is_action_item = Column(Boolean, default=False)
    is_decision = Column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="transcriptions")


class Message(Base):
    """消息内容表 - 存储消息基本信息"""
    __tablename__ = "messages"

    # 主键（BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 内容
    title = Column(String(100), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")

    # 关联用户
    # 注意：将 sender_id 显式声明为外键，以便 SQLAlchemy 正确建立 Message.sender 关系
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="发送者ID（UUID）")

    # 发送者关系 - 关联到 User 模型
    # 说明：为便于在查询中使用 joinedload(Message.sender) 以及在业务代码中访问 msg.sender.user_name
    # 定义从 Message 到 User 的多对一关系。
    sender = relationship("User", foreign_keys=[sender_id], lazy="joined")

    # 时间戳
    # 说明：与数据库 DDL 保持一致，使用 CURRENT_TIMESTAMP 语义
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系 - 与MessageRecipient的一对多关系
    recipients = relationship("MessageRecipient", back_populates="message", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_created_at', 'created_at'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return f"<Message(id={self.id}, title='{self.title}', sender_id={self.sender_id})>"


class MessageRecipient(Base):
    """消息接收者关联表 - 支持多接收者消息功能"""
    __tablename__ = "message_recipients"

    # 主键字段
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 关联字段
    message_id = Column(BigInteger, ForeignKey("messages.id"), nullable=False, comment="消息ID（外键指向 messages.id）")
    recipient_id = Column(String(36), nullable=False, comment="接收者ID（UUID）")

    # 状态字段
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读(0未读/1已读)")
    read_at = Column(DateTime(timezone=True), nullable=True, comment="阅读时间（可选）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间（关联时间）")

    # 关联关系 - 与Message的多对一关系
    message = relationship("Message", back_populates="recipients")

    # 约束与索引 - 与数据库DDL保持一致
    __table_args__ = (
        UniqueConstraint('message_id', 'recipient_id', name='uk_message_recipient'),
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    # 索引设计 - 优化查询性能
    __table_args__ = (
        # 唯一约束：防止重复发送
        Index('uk_message_recipient', 'message_id', 'recipient_id', unique=True),
        # 索引
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return (
            f"<MessageRecipient("
            f"id={self.id}, "
            f"message_id={self.message_id}, "
            f"recipient_id={self.recipient_id}, "
            f"is_read={self.is_read}"
            f")>"
        )


    def mark_as_read(self) -> None:
        """标记消息为已读"""
        self.is_read = True
        self.read_at = datetime.now(shanghai_tz)

    def mark_as_unread(self) -> None:
        """标记消息为未读"""
        self.is_read = False
        self.read_at = None
