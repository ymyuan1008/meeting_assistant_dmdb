# 标准库
import base64
import os
import json
from typing import List, Generator
from datetime import datetime
from typing import List
from typing import Generator
from datetime import datetime, timezone
from pathlib import Path
import pytz
from loguru import logger
from httpx import AsyncClient
from typing import Any, Dict,Optional
import aiofiles

#第三方库
from sqlalchemy.orm import Session
from pydub import AudioSegment
from pydantic import BaseModel

from fastapi import  UploadFile, File
from fastapi import APIRouter,HTTPException, Depends
from fastapi.security import HTTPBearer

#自定义库
from db.databases import DatabaseConfig, DatabaseSessionManager
from db.conn_manager import ConnectionManager
from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from services.auth_dependencies import require_auth

from services.service_models import User,  TranscriptionText, TranslationTextRequest,TranscriptionTextResponse
from schemas import MeetingCreate, MeetingResponse, TranscriptionCreate

# 定义 Token 验证方案（Bearer Token）
security = HTTPBearer()

router = APIRouter(prefix="/api/meetings", tags=["Mettings"])
# 获取东八区当前时间
tz = pytz.timezone("Asia/Shanghai")

# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()
manager = ConnectionManager()

MEETING_NOT_FOUND_DETAIL = "Meeting not found"

# 对外暴露的依赖注入函数
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖
get_async_db = db_manager.get_async_session

@router.get("/open")
async def root()->dict[str, str]:
    return {"message": "Meeting Assistant API is running"}

# Meeting management endpoints
@router.post("/", summary="创建新会议", response_model=MeetingResponse)
async def create_meeting(meeting: MeetingCreate,
                         current_user: User = Depends(require_auth),
                         db: Session = Depends(get_db)) ->MeetingResponse:
    """创建新会议
    Args:
        meeting (MeetingCreate): 会议创建数据，已通过Pydantic验证
        db (Session): 数据库会话
    Returns:
        MeetingResponse: 新创建的会议对象
    Raises:
        HTTPException: 400 - 输入数据无效
        HTTPException: 500 - 服务器内部错误
    """
    user_id = str(current_user.id)
    try:
        # 开始数据库事务
        db.begin()

        # 创建会议记录
        new_meeting = await meeting_service.create_meeting(db, meeting,user_id)

        # 提交事务
        db.commit()

        # 记录成功日志
        logger.info(f"成功创建会议: {new_meeting.id}")

        return new_meeting

    except ValueError as e:
        # 回滚事务
        db.rollback()
        # 记录警告日志
        logger.warning(f"无效的会议数据: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"无效的会议数据: {str(e)}"
        )

    except Exception as e:
        # 回滚事务
        db.rollback()
        # 记录错误日志
        logger.error(f"创建会议失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="服务器内部错误，创建会议失败"
        )

@router.get("/user/", summary="获取全部会议信息", response_model=List[MeetingResponse])
async def get_meetings(current_user: User = Depends(require_auth),
                    db: Session = Depends(get_db))-> list[MeetingResponse]:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user ID")

        # 获取会议列表
        meetings = await meeting_service.get_meetings(db, user_id)

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")

        return meetings
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{meeting_id}/user/", summary="获取单一会议信息", response_model=MeetingResponse)
async def get_meeting(meeting_id: str,
                      current_user: User = Depends(require_auth),
                      db: Session = Depends(get_db)) -> MeetingResponse:
    """获取单一会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user ID")

        # 验证 meeting_id 是否合法
        if not meeting_id or not isinstance(meeting_id, str):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")

        # 获取会议信息并验证用户权限
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        # 记录成功日志
        logger.info(f"Successfully retrieved meeting {meeting_id} for user: {user_id}")

        return meeting
    except HTTPException:
        raise
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meeting {meeting_id} for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{meeting_id}/user/",summary="更新会议信息", response_model=MeetingResponse)
def update_meeting(meeting_id: str,
                   meeting: MeetingCreate,
                   current_user: User = Depends(require_auth), db: Session = Depends(get_db))-> MeetingResponse:
    """更新会议信息"""
    user_id = str(current_user.id)
    updated_meeting = meeting_service.update_meeting(db, meeting_id, meeting,user_id)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return updated_meeting

@router.delete("/{meeting_id}/user/", summary="删除指定会议信息")
async def delete_meeting(meeting_id: str,
                         current_user: User = Depends(require_auth),
                         db: Session = Depends(get_db))-> dict[str, str]:
    """删除指定会议信息"""
    user_id = str(current_user.id)
    success = await meeting_service.delete_meeting(db, meeting_id,user_id)
    if not success:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return {"message": "Meeting deleted successfully"}

# Document generation endpoints
@router.post("/{meeting_id}/generate-notification", summary="生成会议通知文档")
async def generate_notification(meeting_id: str,
                                current_user: User = Depends(require_auth),
                                db: Session = Depends(get_db)) -> dict[str, Any]:
    """生成会议通知文档"""
    user_id = str(current_user.id)
    print("当前用户ID",)
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        print(meeting.title)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        doc_path = await document_service.generate_notification(meeting)
        return {"document_path": doc_path, "message": "Notification generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{meeting_id}/generate-minutes")
async def generate_minutes(meeting_id: str,
                           current_user: User = Depends(require_auth),
                           db: Session = Depends(get_db))-> dict[str, Any]:
    """生成会议纪要文档
    """
    user_id = str(current_user.id)
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
        doc_path = await document_service.generate_minutes(meeting, transcriptions)
        return {"document_path": doc_path, "message": "Meeting minutes generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{meeting_id}/send-notification")
async def send_notification(meeting_id: str, db: Session = Depends(get_db))-> dict[str, str]:
    """
    Send meeting notification emails
    发送会议通知邮件
    """
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        success = await email_service.send_meeting_notification(meeting)
        if success:
            return {"message": "Notification emails sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send emails")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 复用 AsyncClient（避免每次调用创建新连接，提升性能）
async_client = AsyncClient(timeout=5)
# Token 验证（你的服务对客户端的验证）
security = HTTPBearer()

# 外部 wss 地址（目标服务）
EXTERNAL_WSS_URL = (
    "wss://ai.csg.cn/aihear-50-249/app/hisee/websocket/storage/57fb5931-f776-4b18-be59-a137f706a949"
    "?appid=tainsureAssistant,uid=555fd741-5023-4ea8-84ff-b702a087137b,ack=1,pk_on=1"
)
EXTERNAL_ACCESS_TOKEN = "6c0a12ed344841859e486e46fbe1b881"


# 消息模型
class TranslationItem(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    translated_text: str
    confidence: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None

class TranslationBatch(BaseModel):
    items: list[TranslationItem]
    batch_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


# 后台任务：连接外部 wss 服务并接收消息
@router.post("/translate_text_load")
async def translate_text_load(request: TranslationTextRequest, db: Session = Depends(get_db))-> dict[str, Any]:
    """
    接收翻译文本数据并录入数据库

    Args:
        meeting_id: 会议ID
        translate_text: 翻译文本内容
        speaker_name: 说话人姓名（可选）

    Returns:
        dict: 操作结果
    """
    try:
        meeting_id = request.meetingId
        other_meeting_id = request.otherMeetingId
        translate_text = request.translateText
        speaker_name = request.speakerName

        # 验证输入参数
        if not meeting_id:
            raise HTTPException(
                status_code=400,
                detail="会议ID不能为空"
            )

        if not translate_text:
            raise HTTPException(
                status_code=400,
                detail="翻译文本不能为空"
            )

        # 创建新的翻译文本记录
        translation_record = TranscriptionText(
            meeting_id=meeting_id,
            other_meeting_id=other_meeting_id,
            speaker_name=json.dumps(request.extract_conversation_data()['speakers'], ensure_ascii=False),
            text_message=json.dumps(request.translateText, ensure_ascii=False),
            created_time=datetime.now(pytz.timezone('Asia/Shanghai'))
        )


        # 添加到数据库
        db.add(translation_record)
        db.commit()
        db.refresh(translation_record)
        logger.info(f"成功保存翻译文本，会议ID: {meeting_id}, 记录ID: {translation_record.id}")

        return {
            "code": 200,
            "message": "翻译文本保存成功",
            "data": {
                "id": translation_record.id,
                "meeting_id": translation_record.meeting_id,
                "speaker_name": translation_record.speaker_name,
                "created_time": translation_record.created_time.isoformat()
            }
        }

    except HTTPException:
        # 重新抛出已知的HTTP异常
        raise
    except Exception as e:
        # 如果发生全局错误，回滚事务
        if db:
            db.rollback()
        logger.error(f"保存翻译文本时发生错误 - 会议ID: {meeting_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"处理翻译数据时发生错误: {str(e)}"
        )
    finally:
        if db:
            db.close()

@router.get("/{meeting_id}/transcriptions")
async def get_meeting_transcriptions(meeting_id: str, db: Session = Depends(get_db)):
    """Get all transcriptions for a meeting"""
    transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
    return transcriptions


# Upload audio file for transcription
@router.post("/{meeting_id}/upload-audio")
async def upload_audio(
        meeting_id: str,
        audio_file: UploadFile = File(...),
        speaker_id: str = "unknown",
        db: Session = Depends(get_db)
)-> dict[str, Any]:
    """Upload audio file for transcription"""
    try:
        # Save uploaded file temporarily
        # 校验音频格式,mpeg 对应 MP3
        allowed_formats = {"audio/wav", "audio/mpeg"}
        if audio_file.content_type not in allowed_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format. Allowed formats: WAV, MP3"
            )
        # 手动指定 ffmpeg 和 ffprobe 路径（替换为你的实际路径）
        ffmpeg_path = "D:/ffmpeg/bin/ffmpeg.exe"
        ffprobe_path = "D:/ffmpeg/bin/ffprobe.exe"
        # 2. 验证路径是否存在（可选，但能快速排查错误）
        if not os.path.exists(ffprobe_path):
            raise FileNotFoundError(f"ffprobe 不存在于该路径：{ffprobe_path}")

        # 告诉 pydub 工具路径
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffprobe_path

        file_path = f"temp/{audio_file.filename}"
        print("file_path------------------",file_path)
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await audio_file.read()
            buffer.write(content)
        # 读取上传的音频
        audio = AudioSegment.from_file(file_path)
        # 转换为 16kHz 单声道 WAV（语音识别常用格式）

        # 获取原始文件名和扩展名
        original_filename = audio_file.filename
        filename_stem = Path(original_filename).stem  # 获取不带扩展名的文件名部分
        # 构建转换后的文件路径
        converted_path = f"temp/converted_{filename_stem}.wav"
        # 16kHz 单声道
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(converted_path, format="wav")
        # 后续用 converted_path 进行转录
        transcription = await speech_service.transcribe_audio_file(converted_path, speaker_id)

        # Transcribe audio
        #transcription = await speech_service.transcribe_audio_file(file_path, speaker_id)

        if transcription:
            # Save transcription to database
            transcription_record = TranscriptionCreate(
                meeting_id=meeting_id,
                speaker_id=speaker_id,
                text=transcription,
                timestamp=datetime.now(timezone.utc).isoformat() + "Z"
            )
            await meeting_service.save_transcription(db, transcription_record)

            return {"transcription": transcription, "message": "Audio transcribed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Get meeting transcriptions

