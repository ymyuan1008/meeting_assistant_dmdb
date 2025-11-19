# 标准库

import pytz


#第三方库

from sqlalchemy.orm import Session
from fastapi import APIRouter,HTTPException, Depends
from pydantic import BaseModel
from typing import List, Any

#自定义库
from services.sign_in_service import SignInService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from db.conn_manager import ConnectionManager
from db.dm_conn import get_db
from models import User, UserStatus
from schema import SignRequest

# 对外暴露的依赖注入函数
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


def _resp(data=None, message="success", code=200):
    return {"code": code, "message": message, "data": data}


def _raise(status_code: int, message: str, code: str):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

class ApiResponse(BaseModel):
    # 明确要求 data 是列表
    data: List[Any]
    message: str
    code: int

# 获取当前所有人员的签到状态
@router.get("/people", summary="获取当前所有人员的签到状态")
async def get_people_sign_status(meeting_id: str,db: Session = Depends(get_db)):
    """获取所有人员的签到状态"""
    try:
        # 调用服务层方法，传入数据库会话
        people = await attendance_service.get_people_sign_status(db, meeting_id)

        return {"data":people,"code":200, "message":"request success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取人员签到状态失败: {str(e)}")

# 签到接口
@router.post("/sign")
async def sign(
        request: SignRequest,
        db: Session = Depends(get_db)
):
    """人员批量签到接口"""
    current_users_id = request.current_users_id
    meeting_id = request.meeting_id
    if not current_users_id:
        raise HTTPException(status_code=400, detail="用户ID列表不能为空")

    results = []
    errors = []

    for user_id in current_users_id:
        try:
            # 查询用户
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"用户ID {user_id} 不存在")
                continue

            # 调用服务层的签到方法
            result = await attendance_service.sign_person(db, user.name, meeting_id, str(user.id))
            results.append({
                "user_id": user_id,
                "user_name": user.name,
                "status": "success",
                "data": result
            })

        except ValueError as e:
            # 捕获服务层抛出的“未找到人员”异常
            errors.append(f"用户ID {user_id} 签到失败: {str(e)}")
            results.append({
                "user_id": user_id,
                "status": "failed",
                "error": str(e)
            })
        except Exception as e:
            # 捕获其他异常
            errors.append(f"用户ID {user_id} 签到异常: {str(e)}")
            results.append({
                "user_id": user_id,
                "status": "error",
                "error": f"签到操作失败: {str(e)}"
            })

    # 返回批量操作结果
    return {
        "meeting_id": meeting_id,
        "total_count": len(current_users_id),
        "success_count": len([r for r in results if r["status"] == "success"]),
        "failed_count": len([r for r in results if r["status"] == "failed"]),
        "error_count": len([r for r in results if r["status"] == "error"]),
        "results": results,
        "errors": errors if errors else None
    }

@router.post("/leave")
async def leave(
        request: SignRequest,
        db: Session = Depends(get_db)
):
    """
    人员批量请假接口（绑定会议维度）
    """
    current_users_id = request.current_users_id
    meeting_id = request.meeting_id
    if not current_users_id:
        raise HTTPException(status_code=400, detail="用户ID列表不能为空")

    results = []
    errors = []

    for user_id in current_users_id:
        try:
            # 查询用户
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"用户ID {user_id} 不存在")
                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "error": "用户不存在"
                })
                continue

            # 调用服务层请假方法
            result = await attendance_service.leave_person(
                db=db,
                name=user.name,
                meeting_id=meeting_id,
                user_id=str(user_id)
            )
            results.append({
                "user_id": user_id,
                "user_name": user.name,
                "status": "success",
                "data": result
            })

        except HTTPException as e:
            # 捕获服务层抛出的已知异常（如会议/人员不存在）
            errors.append(f"用户ID {user_id} 请假失败: {e.detail}")
            results.append({
                "user_id": user_id,
                "user_name": user.name if user else None,
                "status": "failed",
                "error": e.detail
            })
        except Exception as e:
            # 捕获其他未知异常
            errors.append(f"用户ID {user_id} 请假异常: {str(e)}")
            results.append({
                "user_id": user_id,
                "user_name": user.name if user else None,
                "status": "error",
                "error": f"请假操作失败: {str(e)}"
            })

    # 返回批量操作结果
    return {
        "meeting_id": meeting_id,
        "total_count": len(current_users_id),
        "success_count": len([r for r in results if r["status"] == "success"]),
        "failed_count": len([r for r in results if r["status"] == "failed"]),
        "error_count": len([r for r in results if r["status"] == "error"]),
        "results": results,
        "errors": errors if errors else None
    }


async def leave(
        meeting_id: str,
        current_users_id: list[str],  # 改为列表参数
        db: Session = Depends(get_db)
):
    """
    人员批量请假接口（绑定会议维度）
    """
    if not current_users_id:
        raise HTTPException(status_code=400, detail="用户ID列表不能为空")

    results = []
    errors = []

    for user_id in current_users_id:
        try:
            # 查询用户
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"用户ID {user_id} 不存在")
                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "error": "用户不存在"
                })
                continue

            # 调用服务层请假方法
            result = await attendance_service.leave_person(
                db=db,
                name=user.name,
                meeting_id=meeting_id,
                user_id=str(user_id)
            )
            results.append({
                "user_id": user_id,
                "user_name": user.name,
                "status": "success",
                "data": result
            })

        except HTTPException as e:
            # 捕获服务层抛出的已知异常（如会议/人员不存在）
            errors.append(f"用户ID {user_id} 请假失败: {e.detail}")
            results.append({
                "user_id": user_id,
                "user_name": user.name if user else None,
                "status": "failed",
                "error": e.detail
            })
        except Exception as e:
            # 捕获其他未知异常
            errors.append(f"用户ID {user_id} 请假异常: {str(e)}")
            results.append({
                "user_id": user_id,
                "user_name": user.name if user else None,
                "status": "error",
                "error": f"请假操作失败: {str(e)}"
            })

    # 返回批量操作结果
    return {
        "meeting_id": meeting_id,
        "total_count": len(current_users_id),
        "success_count": len([r for r in results if r["status"] == "success"]),
        "failed_count": len([r for r in results if r["status"] == "failed"]),
        "error_count": len([r for r in results if r["status"] == "error"]),
        "results": results,
        "errors": errors if errors else None
    }
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