from datetime import datetime

# 第三方库
from sqlalchemy import BigInteger, String, Text, ForeignKey, Index, Boolean, func, text
from sqlalchemy import Column, DateTime
from sqlalchemy.orm import relationship


# 自定义库
from models.base import BaseModel


class Message(BaseModel):
    """消息内容表 - 存储消息基本信息"""
    __tablename__ = "messages"

    # 主键（BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 内容
    title = Column(String(100), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")

    # 关联用户
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="发送者ID（UUID）")

    # 发送者关系
    sender = relationship("User", foreign_keys=[sender_id], lazy="selectin")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    # 关联关系 - 与MessageRecipient的一对多关系
    recipients = relationship("MessageRecipient", back_populates="message", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_created_at', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, title='{self.title}', sender_id={self.sender_id})>"


class MessageRecipient(BaseModel):
    """消息接收者关联表 - 支持多接收者消息功能"""
    __tablename__ = "message_recipients"

    # 主键字段
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 关联字段
    message_id = Column(BigInteger, ForeignKey("messages.id"), nullable=False, comment="消息ID")
    recipient_id = Column(String(36), nullable=False, comment="接收者ID（UUID）")

    # 状态字段
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读(0未读/1已读)")
    read_at = Column(DateTime(timezone=True), nullable=True, comment="阅读时间")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    # 关联关系
    message = relationship("Message", back_populates="recipients")

    # 约束与索引
    __table_args__ = (
        Index('uk_message_recipient', 'message_id', 'recipient_id', unique=True),
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    def __repr__(self) -> str:
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
        self.read_at = BaseModel.get_shanghai_time()

    def mark_as_unread(self) -> None:
        """标记消息为未读"""
        self.is_read = False
        self.read_at = None
