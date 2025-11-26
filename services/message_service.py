from typing import List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, delete
from loguru import logger
from datetime import datetime
from pytz import timezone

from  models import Message, MessageRecipient

shanghai_tz = timezone("Asia/Shanghai")

class MessageService(object):
    """消息业务逻辑，实现消息发送、查询与状态更新
    - 兼容用户ID为字符串UUID（与 User.id 对齐）
    """

    def send_message(self,
                           db:Session,
                           sender_id: str,
                           title: str,
                           content: str,
                           recipient_ids: list[str]) -> Message:
        """发送消息：创建 Message 与多个 MessageRecipient 关联记录
        Args:
            db: 数据库会话
            sender_id: 发送者用户ID（字符串或数字字符串）
            title: 消息标题
            content: 消息内容
            recipient_ids: 接收者ID列表（字符串），将转换为 int 存储
        Returns:
            Message: 创建完成的消息对象
        """
        # 验证并标准化ID为字符串
        sid = str(sender_id).strip()
        if not sid:
            raise ValueError("sender_id 不能为空")

        cast_recipient_ids: list[str] = []
        for rid in recipient_ids:
            r = str(rid).strip()
            if not r:
                logger.warning(f"跳过空的接收者ID: {rid}")
                continue
            cast_recipient_ids.append(r)

        if not cast_recipient_ids:
            raise ValueError("recipient_ids 为空或全部无效")

        # 创建消息
        msg = Message(title=title, content=content, sender_id=sid)
        db.add(msg)
        db.flush()

        # 创建接收者关联记录
        for rid_str in cast_recipient_ids:
            mr = MessageRecipient(message_id=msg.id, recipient_id=rid_str, is_read=False)
            db.add(mr)

        db.commit()
        db.refresh(msg)
        return msg

    def list_messages(
            self,
            db: Session,
            recipient_id: str,
            only_unread: bool = False,
            page: int = 1,
            page_size: int = 20
    ) -> tuple[list[Message], int]:
        """
                    查询用户收到的消息列表（分页）
                Args:
                    db: 数据库会话
                    recipient_id: 接收者用户ID（字符串）
                    only_unread: 仅查询未读消息
                    page: 页码，从1开始
                    page_size: 每页数量
                Returns:
                    tuple[list[Message], int]: (消息列表, 总条数)
         """
        # 构建过滤条件
        conditions = [MessageRecipient.recipient_id == recipient_id]
        if only_unread:
            conditions.append(MessageRecipient.is_read == False)

        # 添加调试日志
        logger.info(f"查询用户消息: recipient_id={recipient_id}, only_unread={only_unread}, page={page}, page_size={page_size}")

        # 统计总数：使用子查询对 message_id 去重后计数，避免某些驱动/数据库下 distinct 计数问题
        ids_distinct_subq = (
            select(MessageRecipient.message_id)
            .where(*conditions)
            .group_by(MessageRecipient.message_id)
        ).subquery()
        count_q = select(func.count()).select_from(ids_distinct_subq)
        count_result = db.execute(count_q)
        total = int(count_result.scalar() or 0)

        # 计算偏移
        offset = max(0, (page - 1) * page_size)

        # 先分页获取消息ID，避免 join 集合导致分页偏差
        ids_q = (
            select(Message.id)
            .join(MessageRecipient, MessageRecipient.message_id == Message.id)
            .where(*conditions)
            .group_by(Message.id)
            .offset(offset)
            .limit(page_size)
        )
        ids_result =  db.execute(ids_q)
        id_rows = ids_result.all()
        ids = [row[0] for row in id_rows]

        if not ids:
            return [], total

        # 再按ID查询具体消息，并选择式预加载 recipients（避免重复行）
        data_q = (
            select(Message)
            .where(Message.id.in_(ids))
            .options(selectinload(Message.recipients))
        )
        data_result =  db.execute(data_q)
        messages = data_result.scalars().all()
        return messages, total

    def mark_read(self,
                        db: Session,
                        message_id: str,
                        recipient_id: str) -> bool:
        """标记某条消息为已读
        Args:
            db: 数据库会话
            message_id: 消息ID（字符串），转换为 int
            recipient_id: 接收者ID（字符串），转换为 int
        Returns:
            bool: 是否标记成功
        """
        try:
            mid_int = int(str(message_id))
        except (TypeError, ValueError):
            raise ValueError("message_id 必须是数字或可转换为数字的字符串")
        rid_str = str(recipient_id).strip()
        if not rid_str:
            raise ValueError("recipient_id 不能为空")

        # 添加调试日志
        logger.info(f"尝试标记消息已读: message_id={mid_int}, recipient_id={rid_str}")

        result = db.execute(
            select(MessageRecipient).where(
                (MessageRecipient.message_id == mid_int) & (MessageRecipient.recipient_id == rid_str)
            ).limit(1)
        )
        mr = result.scalar_one_or_none()

        if not mr:
            logger.warning(f"未找到消息记录: message_id={mid_int}, recipient_id={rid_str}")
            # 查询所有该用户的消息记录用于调试
            all_records = db.execute(
                select(MessageRecipient).where(MessageRecipient.recipient_id == rid_str)
            ).scalars().all()
            logger.info(f"用户 {rid_str} 的所有消息记录: {[{'message_id': r.message_id, 'is_read': r.is_read} for r in all_records]}")
            return False

        logger.info(f"找到消息记录，更新前状态: is_read={mr.is_read}")
        mr.is_read = True
        mr.read_at = datetime.now(shanghai_tz)

        # 提交前再次检查状态
        logger.info(f"更新后状态: is_read={mr.is_read}, read_at={mr.read_at}")

        # 注意：不再手动提交，让 FastAPI 的依赖注入自动处理
        # db.commit() # 注释掉手动提交
        logger.info(f"数据更新完成，等待FastAPI自动提交: message_id={mid_int}, recipient_id={rid_str}")

        return True

    def mark_read_batch(self,
                              db: Session,
                              recipient_id: str,
                              message_ids: list[str]) -> int:
        """批量标记多条消息为已读（针对当前用户）
        Args:
            db: 数据库会话
            recipient_id: 接收者ID（字符串或数字字符串）
            message_ids: 消息ID列表（字符串形式）
        Returns:
            int: 成功标记为已读的关联记录数量
        """
        # 过滤并转换消息ID
        cast_message_ids: list[int] = []
        for mid in message_ids:
            try:
                cast_message_ids.append(int(str(mid)))
            except (TypeError, ValueError):
                logger.warning(f"跳过无效的消息ID: {mid}")

        if not cast_message_ids:
            return 0

        # 查询当前用户且未读的关联记录
        rows = db.execute(
            select(MessageRecipient).where(
                (MessageRecipient.recipient_id == recipient_id) &
                (MessageRecipient.message_id.in_(cast_message_ids)) &
                (MessageRecipient.is_read == False)
            )
        )
        recipients = rows.scalars().all()
        if not recipients:
            return 0

        now_ts = datetime.now(shanghai_tz)
        for mr in recipients:
            mr.is_read = True
            mr.read_at = now_ts

        # 不再手动提交，让 FastAPI 的依赖注入自动处理
        # db.commit()
        logger.info(f"批量更新完成，等待FastAPI自动提交: 更新数量={len(recipients)}")
        return len(recipients)

    def delete_message_links(self,
                                   db: Session,
                                   recipient_id: str,
                                   is_read: bool | None = None,
                                   message_id: str | None = None) -> int:
        """
                删除消息与当前用户的关联（仅删除关联表数据）
                Args:
                    db: 数据库会话
                    recipient_id: 当前用户ID（字符串）
                    is_read: 根据阅读状态过滤删除（True=已读, False=未读, None=不限）
                    message_id: 指定要删除关联的消息ID（可选）
                Returns:
                    int: 删除的关联记录数量
                """
        rid_str = str(recipient_id).strip()
        if not rid_str:
            raise ValueError("recipient_id 不能为空")

        conditions = [MessageRecipient.recipient_id == rid_str]
        if is_read is not None:
            conditions.append(MessageRecipient.is_read == bool(is_read))
        if message_id is not None:
            try:
                mid_int = int(str(message_id))
                conditions.append(MessageRecipient.message_id == mid_int)
            except (TypeError, ValueError):
                raise ValueError("message_id 必须是数字或可转换为数字的字符串")

        if len(conditions) == 1:
            raise ValueError("必须提供 is_read 或 message_id 之一，以限制删除范围")

        result = db.execute(
            delete(MessageRecipient).where(*conditions)
        )
        # 不再手动提交，让 FastAPI 的依赖注入自动处理
        # db.commit()
        deleted_count = int(result.rowcount or 0)
        logger.info(f"删除操作完成，等待FastAPI自动提交: 删除数量={deleted_count}")
        return deleted_count
