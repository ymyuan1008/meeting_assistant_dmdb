# 标准库
import os
import json
import uuid

import pytz
import ssl
import traceback

from typing import List, Generator
from typing import Any, Dict,Optional
from datetime import datetime
from loguru import logger


#第三方库
from sqlalchemy.orm import Session

from fastapi import UploadFile, File, Form, status
from fastapi import APIRouter,HTTPException, Depends

#自定义库

from db.dm_conn import get_db
from db.conn_manager import ConnectionManager

from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from services.auth_dependencies import require_auth

from models  import User,  Attachment, Meeting, TranscriptionText,  Transcription
from schema  import  TranslationTextRequest,MeetingCreate,MeetingUpdate, MeetingResponse
from schema  import  MeetingApiResponse,MeetingListApiResponse,DailyWorkRequest,DailyWorkApiResponse
from schema  import  FileApiResponse,LedgerInfoRequest,LedgerApiResponse
from db.minio_upload import MinioUploader

# 全局常量定义
MINIO_UPLOAD_FAILED = "MinIO 上传失败，返回本地文件路径。"
MEETING_DATA_JSON_FORMAT_ERROR = "会议数据格式错误，必须是有效的JSON"
MEETING_DATA_PARAM_DESCRIPTION = "会议数据(JSON字符串)"
RESPONSE_SUCCESS_MESSAGE = "request success"
INVALID_USER_ID_ERROR = "Invalid user ID"
INTERNAL_SERVER_ERROR = "Internal server error"
DOWNLOAD_SUCCESS_MESSAGE = "download success"
SHANGHAI_TIMEZONE = "Asia/Shanghai"



# 创建不验证证书的 SSL 上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False  # 不验证主机名
ssl_context.verify_mode = ssl.CERT_NONE  # 不验证证书

router = APIRouter(prefix="/api/meetings", tags=["Mettings"])
# 获取东八区当前时间
tz = pytz.timezone(SHANGHAI_TIMEZONE)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")



def _init_minio_uploader() -> Optional[MinioUploader]:
    """Safely initialize MinIO uploader. Returns None if config missing/invalid."""
    endpoint = os.getenv('MINIO_ENDPOINT')
    access_key = os.getenv('MINIO_ACCESS_KEY')
    secret_key = os.getenv('MINIO_SECRET_KEY')
    secure = str(os.getenv('MINIO_SECURE', 'False')).lower() == 'true'
    cert_check = False

    if not endpoint or not access_key or not secret_key:
        logger.warning("MinIO 未配置（缺少 MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY），将使用本地保存。")
        return None
    try:
        return MinioUploader(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    except Exception as e:
        logger.error(f"MinIO 初始化失败，将使用本地保存。错误: {e}")
        return None

uploader: Optional[MinioUploader] = _init_minio_uploader()
console_address = os.getenv('MINIO_CONSOLE_ADDRESS')
bucket_name = "meeting-minutes"


# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()
manager = ConnectionManager()

MEETING_NOT_FOUND_DETAIL = "Meeting not found"



async def handle_file_upload(file: UploadFile, user_id: str) -> dict[str, Any]:
    """处理单个文件上传

    Args:
        file: 上传的文件对象
        user_id: 用户ID

    Returns:
        附件信息字典
    """
    try:
        # 验证文件类型
        allowed_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }

        # 获取文件扩展名
        file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''

        if file_extension not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_extension}，支持的类型: {', '.join(allowed_types.keys())}"
            )

        # 验证文件大小（20MB限制）
        max_size = 20 * 1024 * 1024
        content = await file.read()
        file_size = len(content)

        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail="文件大小不能超过20MB"
            )

        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_name = file.filename
        object_name = file_name

        # 创建上传目录
        upload_dir = "uploads/meetings"
        os.makedirs(upload_dir, exist_ok=True)

        # 保存文件
        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, file_path, object_name)
            if minio_path and presigned_url:
                print(f"文件已上传，MinIO 路径: {minio_path}")
                print(f"预签名 URL: {presigned_url}")

            else:
                logger.warning(MINIO_UPLOAD_FAILED)
        except Exception as e:
            logger.error(f"MinIO 上传异常，返回本地文件路径。错误: {e}")

        # 返回附件信息（符合Attachment模型格式）
        return {
            "file_name": file_name,
            "file_path": file_path,
            "download_url": presigned_url,
            "file_size": file_size,
            "content_type": allowed_types[file_extension],
            "uploaded_by": user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail="文件上传失败")

def validate_field(value: int| str, field_name: str) -> None:
    """验证必填字段是否为空"""
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name}不能为空"
        )

@router.get("/open")
async def root()->dict[str, str]:
    return {"message": "Meeting Assistant API is running"}

@router.get("/user/", summary="获取全部会议信息", response_model=MeetingListApiResponse)
async def get_meetings(current_user: User = Depends(require_auth),
                    db: Session = Depends(get_db))-> MeetingListApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取会议列表
        meetings = await meeting_service.get_meetings(db, user_id)

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        return {"data": meetings, "code": 200, "message": RESPONSE_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.get("/{meeting_id}/user/", summary="获取单一会议信息", response_model=MeetingApiResponse)
async def get_meeting(meeting_id: str,
                      current_user: User = Depends(require_auth),
                      db: Session = Depends(get_db)) -> MeetingResponse:
    """获取单一会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 验证 meeting_id 是否合法
        if not meeting_id or not isinstance(meeting_id, str):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")

        # 获取会议信息并验证用户权限
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        # 记录成功日志
        logger.info(f"Successfully retrieved meeting {meeting_id} for user: {user_id}")
        return {"data": meeting, "code": 200, "message": RESPONSE_SUCCESS_MESSAGE}

    except HTTPException:
        raise
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meeting {meeting_id} for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

# Meeting management endpoints
@router.post("/", summary="创建新会议", response_model=MeetingApiResponse)
async def create_meeting(
        meeting_data: str = Form(..., description=MEETING_DATA_PARAM_DESCRIPTION),
        files: list[UploadFile] = File([], description="会议附件（可选）"),
        current_user: User = Depends(require_auth),
        db: Session = Depends(get_db)
) -> MeetingApiResponse:
    """创建新会议并支持附件上传

    Args:
        meeting_data (str): 会议数据的JSON字符串
        files (List[UploadFile]): 上传的会议附件列表
        current_user (User): 当前认证用户
        db (Session): 数据库会话

    Returns:
        MeetingResponse: 新创建的会议对象
    """
    user_id = str(current_user.id)

    try:
        if db.in_transaction():
            logger.warning("当前会话已存在活跃事务，尝试结束现有事务")
            db.rollback()  # 若存在未完成事务，先回滚（或根据业务选择commit）
        # 解析会议数据
        meeting_dict = json.loads(meeting_data)
        meeting_create = MeetingCreate(**meeting_dict)

        # 开始数据库事务
        db.begin()
        # 处理文件上传
        attachments_data = []
        if files:
            for file in files:
                attachment_info = await handle_file_upload(file, user_id)
                attachments_data.append(attachment_info)

        # 将附件信息添加到会议数据中
        meeting_create.attachments = attachments_data

        # 创建会议记录
        new_meeting = await meeting_service.create_meeting(db, meeting_create, user_id)

        # 提交事务
        db.commit()

        logger.info(f"成功创建会议: {new_meeting.id}, 附件数量: {len(attachments_data)}")
        return {"data": new_meeting, "code": 200, "message": "创建会议成功"}

    except json.JSONDecodeError as e:
        db.rollback()
        logger.warning(f"JSON解析错误: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=MEETING_DATA_JSON_FORMAT_ERROR
        )
    except ValueError as e:
        db.rollback()
        logger.warning(f"无效的会议数据: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"创建会议失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误，创建会议失败")

@router.post("/batch_create", summary="批量创建新会议")
async def create_meetings_batch(
        meeting_data: str = Form(..., description=MEETING_DATA_PARAM_DESCRIPTION),
        files: list[UploadFile] = File([], description="会议附件（可选）"),
        current_user: User = Depends(require_auth),
        db: Session = Depends(get_db)
):
    """创建新会议并支持附件上传

    Args:
        meeting_data (str): 会议数据的JSON字符串
        files (List[UploadFile]): 上传的会议附件列表
        current_user (User): 当前认证用户
        db (Session): 数据库会话

    Returns:
        MeetingResponse: 新创建的会议对象
    """
    user_id = str(current_user.id)

    try:
        # 解析会议数据
        meeting_dict = json.loads(meeting_data)
        meeting_create = MeetingCreate(**meeting_dict)

        # 开始数据库事务
        db.begin()
        # 处理文件上传
        attachments_data = []
        if files:
            for file in files:
                attachment_info = await handle_file_upload(file, user_id)
                attachments_data.append(attachment_info)

        # 将附件信息添加到会议数据中
        meeting_create.attachments = attachments_data

        # 创建会议记录
        new_meeting = await meeting_service.create_meeting(db, meeting_create, user_id)

        # 提交事务
        db.commit()

        logger.info(f"成功创建会议: {new_meeting.id}, 附件数量: {len(attachments_data)}")
        return {"data": new_meeting, "code": 200, "message": "创建会议成功"}

    except json.JSONDecodeError as e:
        db.rollback()
        logger.warning(f"JSON解析错误: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=MEETING_DATA_JSON_FORMAT_ERROR
        )
    except ValueError as e:
        db.rollback()
        logger.warning(f"无效的会议数据: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"创建会议失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误，创建会议失败")

@router.put("/{meeting_id}/user/", summary="更新会议信息", response_model=MeetingApiResponse)
async def update_meeting(
        meeting_id: str,
        meeting_data: str = Form(..., description=MEETING_DATA_PARAM_DESCRIPTION),
        current_user: User = Depends(require_auth),
        db: Session = Depends(get_db)
) -> MeetingApiResponse:
    """更新会议信息，支持修改会议内容和附件上传

    Args:
        meeting_id (str): 会议ID
        meeting_data (str): 会议数据的JSON字符串
        current_user (User): 当前认证用户
        db (Session): 数据库会话

    Returns:
        MeetingResponse: 更新后的会议对象
    """
    user_id = str(current_user.id)

    try:
        if db.in_transaction():
            logger.warning("当前会话已存在活跃事务，尝试结束现有事务")
            db.rollback()  # 若存在未完成事务，先回滚（或根据业务选择commit）
        # 解析会议数据
        meeting_dict = json.loads(meeting_data)
        # 注意：此处根据实际需求使用MeetingUpdate模型（而非创建时的MeetingCreate）
        meeting_update = MeetingUpdate(**meeting_dict)

        # 开始数据库事务
        db.begin()

        # 调用服务层更新会议
        updated_meeting = await meeting_service.update_meeting(
             meeting_id, meeting_update, db, user_id
        )
        if not updated_meeting:
            db.rollback()
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        # 提交事务
        db.commit()
        return {"data": updated_meeting, "code": 200, "message": "Successfully updated the meeting"}

    except json.JSONDecodeError as e:
        db.rollback()
        logger.warning(f"JSON解析错误: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=MEETING_DATA_JSON_FORMAT_ERROR
        )
    except ValueError as e:
        db.rollback()
        logger.warning(f"无效的会议数据: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"更新会议失败: 异常类型={type(e)}, 异常信息={str(e)}, 异常堆栈={traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="服务器内部错误，更新会议失败")

@router.post("/{meeting_id}/attachments", summary="为会议添加附件")
async def add_attachment(
        meeting_id: str,
        files: list[UploadFile] = File(..., description="上传的文件列表"),
        current_user: User = Depends(require_auth),
        db: Session = Depends(get_db)
):
    """
    为指定会议添加一个或多个附件

    支持同时上传多个文件
    """
    # 1. 验证会议存在性（使用first()而非one()避免无结果时抛异常）
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会议 ID {meeting_id} 不存在"
        )

    # 2. 验证文件列表非空
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个文件"
        )

    user_id = current_user.id
    attachments_data: list[dict[str, Any]] = []
    attachment_instances: list[Attachment] = []

    try:
        # 3. 处理文件上传并创建附件实例
        for file in files:
            # 验证文件格式（根据业务需求添加，示例）
            if not file.filename or not file.filename.endswith(('.doc', '.docx', '.pdf', '.txt')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的文件格式：{file.filename}，仅允许 doc/docx/pdf/txt"
                )

            # 处理文件上传（假设handle_file_upload返回包含文件信息的字典）
            file_info = await handle_file_upload(file, user_id)

            # 创建Attachment模型实例
            attachment = Attachment(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                file_name=file_info['file_name'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                download_url=file_info['download_url'],
                content_type=file_info['content_type'],
                uploaded_by=user_id,  # 直接使用当前用户ID，避免依赖上传工具返回
                uploaded_at=datetime.now()
            )

            attachments_data.append(file_info)
            attachment_instances.append(attachment)

        # 4. 批量添加附件并关联会议（优化SQL操作）
        db.add_all(attachment_instances)
        db.commit()  # 一次提交，减少数据库交互

        # 5. 刷新实例以获取数据库生成的字段（如需要）
        for attachment in attachment_instances:
            db.refresh(attachment)

        return {
            "success": True,
            "message": f"成功上传 {len(attachments_data)} 个附件",
            "count": len(attachments_data),
            "attachments": attachments_data
        }

    except Exception as e:
        # 发生异常时回滚事务
        db.rollback()
        # 记录错误日志（建议使用logger）
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"附件上传失败：{str(e)}"
        )


@router.delete("/{meeting_id}/attachments/{attachment_id}", summary="删除会议附件")
async def delete_attachment(meeting_id: str,
                            attachment_id: str,
                            current_user: User = Depends(require_auth),
                            db: Session = Depends(get_db)
                            ) -> dict[str, Any]:
    """
    删除指定的会议附件
    """
    # 检查会议是否存在
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会议 ID {meeting_id} 不存在"
        )

    # 检查附件是否存在
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id,
                                             Attachment.meeting_id == meeting_id ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    # 删除附件
    db.delete(attachment)

    return {
        "success": True,
        "message": "附件删除成功"
    }


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

        transcriptions = await meeting_service.get_transcription_message(db, meeting_id)
        doc_path = await document_service.generate_minutes(meeting, transcriptions)
        download_file = {"document_path": doc_path}

        return {"data": download_file, "code": 200, "message": "Meeting minutes generated successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{meeting_id}/generate-notification", summary="生成会议通知文档")
async def generate_notification(meeting_id: str,
                                current_user: User = Depends(require_auth),
                                db: Session = Depends(get_db)) -> dict[str, Any]:
    """生成会议通知文档"""
    user_id = str(current_user.id)
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        doc_path = await document_service.generate_notification(meeting)
        download_file = {"document_path": doc_path}

        return {"data": download_file, "code": 200, "message": "Meeting Notices generated successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch(
    "/{meeting_id}/status/completed",
    summary="更新会议状态为已完成"
)
async def update_meeting_status_completed(
        meeting_id: str,
        current_user: User = Depends(require_auth),
        db: Session = Depends(get_db)
):
    """
    更新会议状态为已完成（completed）

    - **meeting_id**: 会议的唯一标识符
    - **返回**: 更新成功的响应
    """
    user_id = str(current_user.id)
    try:
        # 验证 user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user ID")

        # 验证 meeting_id 是否合法
        if not meeting_id or not isinstance(meeting_id, str):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")

        # 更新会议状态
        update_success = await meeting_service.modify_meeting_status(db, meeting_id, "completed")

        if not update_success:
            raise HTTPException(status_code=404, detail="Meeting not found or already completed")

        # 记录成功日志
        logger.info(f"Successfully updated meeting {meeting_id} status to 'completed' for user: {user_id}")
        return {"data": None, "code": 200, "message": "会议状态更新成功"}

    except HTTPException:
        raise
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to update meeting {meeting_id} status for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        created_time = datetime.now(tz)
        meeting_id = request.meetingId
        other_meeting_id = request.otherMeetingId
        translate_text = request.translateText
        speaker_name = request.speakerName

        # 使用辅助函数进行参数验证
        validate_field(meeting_id, "会议ID")
        validate_field(translate_text, "翻译文本")

        # 创建新的翻译文本记录
        translation_record = TranscriptionText(
            meeting_id=meeting_id,
            other_meeting_id=other_meeting_id,
            speaker_name=json.dumps(request.extract_conversation_data()['speakers'], ensure_ascii=False),
            text_message=json.dumps(request.translateText, ensure_ascii=False),
            created_time=created_time
        )
        # 添加到数据库
        db.add(translation_record)
        db.commit()
        db.refresh(translation_record)
        logger.info(f"成功保存翻译文本，会议ID: {meeting_id}, 记录ID: {translation_record.id}")

        original_text = request.extract_conversation_data()['full_text']
        translated_text = request.translateText['audioTranslationData']

        combined_text = f"""原文:{original_text}音频文件转译:{translated_text}"""
        # 创建规整化翻译文本记录
        video_translation_text = Transcription(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            speaker_name=json.dumps(request.extract_conversation_data()['speakers'], ensure_ascii=False),
            text_message=combined_text,
            created_time=created_time
        )
        # 添加到数据库
        db.add(video_translation_text)
        db.commit()
        db.refresh(video_translation_text)

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

@router.post("/daily_work/", summary="履行工作日志")
async def get_daily_info(request: DailyWorkRequest,
                         current_user: User = Depends(require_auth),
                         db: Session = Depends(get_db))-> DailyWorkApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    participants_list = request.participants_code
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取会议列表
        meetings = await meeting_service.get_daily_work(db,user_id,participants_list)

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        return {"data": meetings, "code": 200, "message": RESPONSE_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/daily_work_export/", summary="导出工作日志")
async def export_daily_info(request: DailyWorkRequest,
                    current_user: User = Depends(require_auth),
                    db: Session = Depends(get_db))->FileApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    participants_list = request.participants_code
    meeting_ids = request.meeting_code
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取履职日志信息
        file_info = await meeting_service.export_daily_work(db, user_id, participants_list, meeting_ids)
        file_path = file_info['file_path']
        object_name = file_info['file_name']

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, file_path, object_name)
            if minio_path and presigned_url:
                print(f"文件已上传，MinIO 路径: {minio_path}")
                print(f"预签名 URL: {presigned_url}")
            else:
                logger.warning(MINIO_UPLOAD_FAILED)
        except Exception as e:
            logger.error(f"MinIO 上传异常，返回本地文件路径。错误: {e}")
        down_file_info = {"download_url": presigned_url}
        return {"data": down_file_info , "code": 200, "message": DOWNLOAD_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/daily_work_template/", summary="履职工作日志下载模板")
async def daily_work_template(current_user: User = Depends(require_auth),
                              db: Session = Depends(get_db)) ->FileApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取履职日志信息
        file_name = "履职工作日志模板.xlsx"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        # 构建绝对路径
        file_path = os.path.join(parent_dir, 'uploads', file_name)
        object_name =  f"履职工作日志模板_{timestamp}.xlsx"

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, file_path, object_name)
            if minio_path and presigned_url:
                print(f"文件已上传，MinIO 路径: {minio_path}")
                print(f"预签名 URL: {presigned_url}")

            else:
                logger.warning(MINIO_UPLOAD_FAILED)
        except Exception as e:
            logger.error(f"MinIO 上传异常，返回本地文件路径。错误: {e}")

        down_file_info = {"download_url": presigned_url}
        return {"data": down_file_info, "code": 200, "message": DOWNLOAD_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/ledger_info_query/", summary="查询台账信息")
async def get_ledger_info(current_user: User = Depends(require_auth),
                         db: Session = Depends(get_db))-> LedgerApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)

    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取会议列表
        meetings = await meeting_service.get_ledger_info(db,user_id)

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        return {"data": meetings, "code": 200, "message": RESPONSE_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)


@router.post("/ledger_info_export/", summary="导出台账信息")
async def export_ledger_info(request: LedgerInfoRequest,
                    current_user: User = Depends(require_auth),
                    db: Session = Depends(get_db))->FileApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    agenda_ids = request.agenda_id
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取履职日志信息
        file_info = await meeting_service.export_ledger_info(db, user_id, agenda_ids)
        file_path = file_info['file_path']
        object_name = file_info['file_name']

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, file_path, object_name)
            if minio_path and presigned_url:
                print(f"文件已上传，MinIO 路径: {minio_path}")
                print(f"预签名 URL: {presigned_url}")
            else:
                logger.warning(MINIO_UPLOAD_FAILED)
        except Exception as e:
            logger.error(f"MinIO 上传异常，返回本地文件路径。错误: {e}")

        down_file_info = {"download_url": presigned_url}
        return {"data": down_file_info, "code": 200, "message": DOWNLOAD_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/ledger_manage_template/", summary="导出台账管理下载模板")
async def ledger_manage_template(current_user: User = Depends(require_auth),
                    db: Session = Depends(get_db))->FileApiResponse:
    """获取全部会议信息"""
    user_id = str(current_user.id)
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail=INVALID_USER_ID_ERROR)

        # 获取履职日志信息
        file_name = "台账登记模板.xlsx"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        # 构建绝对路径
        file_path = os.path.join(parent_dir, 'uploads', file_name)
        object_name = f"台账登记模板_{timestamp}.xlsx"

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")
        try:
            minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, file_path, object_name)
            if minio_path and presigned_url:
                print(f"文件已上传，MinIO 路径: {minio_path}")
                print(f"预签名 URL: {presigned_url}")
            else:
                logger.warning("MinIO 上传失败，返回本地文件路径。")

        except Exception as e:
            logger.error(f"MinIO 上传异常，返回本地文件路径。错误: {e}")
        down_file_info = {"download_url": presigned_url}
        return {"data": down_file_info, "code": 200, "message": DOWNLOAD_SUCCESS_MESSAGE}

    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)



# Get meeting transcriptions
@router.get("/{meeting_id}/transcriptions")
async def get_meeting_transcriptions(meeting_id: str, db: Session = Depends(get_db)):
    """Get all transcriptions for a meeting"""
    transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
    return transcriptions







