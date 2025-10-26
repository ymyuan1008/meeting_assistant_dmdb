# 标准库
import base64
import os
import json
from typing import List
from typing import Generator
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
import pytz
from loguru import logger
from httpx import AsyncClient

#第三方库
from fastapi import  WebSocket, WebSocketDisconnect, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from pydub import AudioSegment
from fastapi import APIRouter,HTTPException, Depends

#自定义库
from services.sign_in_service import SignInService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from schemas import MeetingCreate, MeetingResponse, TranscriptionCreate, PersonSignResponse,ParticipantCreate
from db.conn_manager import ConnectionManager
from db.databases import DatabaseConfig, DatabaseSessionManager

from services.auth_dependencies import require_auth, require_admin

from services.service_models import User, UserStatus, UserRole

# 对外暴露的依赖注入函数
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖
get_async_db = db_manager.get_async_session  #

router = APIRouter()
# 获取东八区当前时间
tz = pytz.timezone("Asia/Shanghai")

# Services
attendance_service = SignInService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()

manager = ConnectionManager()

MEETING_NOT_FOUND_DETAIL = "Meeting not found"


router = APIRouter(prefix="/api/attendance", tags=["SignIn"])

# 获取当前所有人员的签到状态
@router.get("/people", summary="获取当前所有人员的签到状态", response_model=List[PersonSignResponse])
async def get_people_sign_status(meeting_id: str,db: Session = Depends(get_db)) -> List[PersonSignResponse]:
    """获取所有人员的签到状态"""
    try:
        # 调用服务层方法，传入数据库会话
        people = await attendance_service.get_people_sign_status(db, meeting_id)
        return people
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取人员签到状态失败: {str(e)}")

# 签到接口
@router.post("/sign")
async def sign(
    meeting_id: str,
    current_user_id: str,
    db: Session = Depends(get_db)
):
    """人员签到接口"""
    # 避免强制转整型，兼容UUID字符串ID
    user = db.query(User).filter(User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在或ID不匹配")
    try:
        # 调用服务层的签到方法，传入姓名和数据库会话
        result = await attendance_service.sign_person(db, user.name, meeting_id, str(user.id))
        return result
    except ValueError as e:
        # 捕获服务层抛出的“未找到人员”异常
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 捕获其他异常（如数据库错误）
        raise HTTPException(status_code=500, detail=f"签到操作失败: {str(e)}")

@router.post("/leave")
async def leave(
    meeting_id: str,
    current_user_id: str,
    db: Session = Depends(get_db)
):
    """
    人员请假接口（绑定会议维度）
    """
    user_id = current_user_id
    user = db.query(User).filter(User.id == user_id).first()
    print("当前姓名是",user.name)
    try:
        # 调用服务层请假方法，传入姓名、会议ID和数据库会话
        result = await attendance_service.leave_person(
            db=db,
            name=user.name,
            meeting_id=meeting_id,
            user_id=str(user_id)
        )
        return result
    except HTTPException as e:
        # 捕获服务层抛出的已知异常（如会议/人员不存在）
        raise e
    except Exception as e:
        # 捕获其他未知异常
        raise HTTPException(status_code=500, detail=f"请假操作失败: {str(e)}")

@router.post("/close")
async def close_sign(
    meeting_id: str,
    db: Session = Depends(get_db)
):
    """
    关闭指定会议的签到功能，重置该会议内所有人员的签到/请假状态
    """
    try:
        # 调用服务层方法，传入会议ID和数据库会话
        result = await attendance_service.close_meeting_sign(
            db=db,
            meeting_id=meeting_id
        )
        return result
    except HTTPException as e:
        # 捕获服务层抛出的已知异常（如会议不存在）
        raise e
    except Exception as e:
        # 捕获其他未知异常
        raise HTTPException(status_code=500, detail=f"关闭操作失败: {str(e)}")