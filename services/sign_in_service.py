# 标准库
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# 自定义类
from .service_models import Meeting, Participant, Transcription, PersonSign, User
from schemas import MeetingCreate,TranscriptionCreate, PersonSignCreate

class SignInService(object):
    async def get_people_sign_status(self, db: Session, meeting_id: str) -> List[PersonSign]:
        """查询所有人员的签到状态（从数据库）"""
        # 可添加排序、过滤等逻辑（如按姓名排序）
        # 1. 验证会议存在性（会议不存在直接抛404，而非返回None）
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )
        return db.query(PersonSign).filter(PersonSign.meeting_id==meeting_id).order_by(PersonSign.name).all()

    async def sign_person(self, db: Session, name: str, meeting_id: str, user_id: str) -> Dict[str, str]:
        """
        处理人员签到逻辑（绑定会议维度，确保签到状态仅对当前会议生效）
        :param db: 数据库会话
        :param name: 人员姓名
        :param meeting_id: 会议ID（字符串类型，适配原参数）
        :return: 签到结果消息
        """
        # 1. 验证会议存在性（会议不存在直接抛404，而非返回None）
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )

        # 2. 验证人员存在性（人员不存在抛404，而非仅打印日志）
        person = db.query(Participant).filter(Participant.name == name, Participant.meeting_id == meeting_id).first()
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 未找到人员 {name}"
            )

        # 3. 查找“人员-会议”关联的签到记录（核心：绑定会议维度，避免全局状态污染）
        # 注意：此处需用数据库模型 PersonSign，而非 Pydantic 模型 PersonSignCreate
        user_meeting_sign = db.query(PersonSign).filter(
            PersonSign.name == name,
            PersonSign.meeting_id == meeting_id
        ).first()

        # 4. 无关联记录则创建（用数据库模型实例，而非Pydantic实例）
        if not user_meeting_sign:
            # 创建当前会议的人员签到记录（与User.id对齐为字符串UUID）
            user_meeting_sign = PersonSign(
                name=name,
                user_code=str(user_id) if user_id is not None else None,
                meeting_id=meeting_id,
                is_signed=False,  # 初始未签到
                is_on_leave=False  # 初始未请假
            )
            db.add(user_meeting_sign)  # 数据库模型可正常添加

        # 5. 更新当前会议的签到状态（仅修改“人员-会议”关联记录，而非全局人员状态）
        # 错误修正：原代码修改 person（全局状态），现改为修改 user_meeting_sign（会议维度状态）
        user_meeting_sign.is_signed = True
        user_meeting_sign.is_on_leave = False

        # 6. 提交事务并刷新（确保获取最新数据库状态）
        try:
            db.commit()
            db.refresh(user_meeting_sign)  # 刷新关联记录实例，而非全局person实例
        except Exception as e:
            db.rollback()  # 事务失败回滚，避免数据异常
            raise HTTPException(
                status_code=500,
                detail=f"签到事务提交失败：{str(e)}"
            )

        # 7. 返回带会议信息的明确消息（提升用户体验）
        return {
            "message": f"{name} 在会议【{meeting.title}】（ID：{meeting_id}）中签到成功",
            "meeting_id": meeting_id,
            "is_signed": user_meeting_sign.is_signed
        }

    async def leave_person(self, db: Session, name: str, meeting_id: str, user_id: str) -> Dict[str, str]:
        """
        处理指定会议的人员请假逻辑
        :param db: 数据库会话
        :param name: 人员姓名
        :param meeting_id: 会议ID（限制请假仅对当前会议有效）
        :return: 请假结果消息
        """
        # 1. 验证会议是否存在
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )

        # 2. 验证人员是否存在
        person = db.query(Participant).filter(Participant.name == name, Participant.meeting_id == meeting_id).first()
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 未找到人员 {name}"
            )

        # 3. 查找该人员在当前会议中的关联记录（无记录则自动创建）
        user_meeting = db.query(PersonSign).filter(
            PersonSign.name == name,
            PersonSign.meeting_id == meeting_id
        ).first()

        if not user_meeting:
            # 自动创建“人员-会议”关联记录（默认未请假状态）
            user_meeting = PersonSign(
                name=name,
                meeting_id=meeting_id,
                user_code=str(user_id) if user_id is not None else None,
                is_signed=False,
                is_on_leave=False
            )
            db.add(user_meeting)

        # 4. 更新请假状态（仅对当前会议生效，同时取消签到状态）
        user_meeting.is_on_leave = True
        user_meeting.is_signed = False

        # 5. 提交事务（带回滚机制）
        try:
            db.commit()
            db.refresh(user_meeting)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"请假事务提交失败: {str(e)}"
            )

        # 6. 返回包含会议信息的结果
        return {
            "message": f"{name} 在会议【{meeting.title}】（ID：{meeting_id}）中请假成功",
            "meeting_id": meeting_id,
            "is_on_leave": user_meeting.is_on_leave
        }

    async def close_meeting_sign(self, db: Session, meeting_id: str) -> Dict[str, str]:
        """
        关闭指定会议的签到，重置该会议内所有人员的签到/请假状态
        :param db: 数据库会话
        :param meeting_id: 会议ID（仅操作该会议的记录）
        :return: 操作结果消息
        """
        # 1. 验证会议是否存在
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )

        # 2. 仅重置该会议下所有人员的签到状态（不影响其他会议）
        affected_rows = db.query(PersonSign).filter(
            PersonSign.meeting_id == meeting_id
        ).update({
            "is_signed": False,
            "is_on_leave": False
        })

        # 3. 提交事务（带回滚机制）
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"重置状态事务提交失败: {str(e)}"
            )

        # 4. 返回包含会议信息的结果（说明重置的范围）
        return {
            "message": f"已关闭会议【{meeting.title}】（ID：{meeting_id}）的签到，共重置 {affected_rows} 条人员状态记录",
            "meeting_id": meeting_id,
            "affected_rows": affected_rows  # 明确告知重置了多少条记录
        }

