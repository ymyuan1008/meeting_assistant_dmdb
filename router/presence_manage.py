from typing import Optional, Dict, Any, Generator
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from sqlalchemy.orm import Session

from db.conn_manager import ConnectionManager
from db.databases import DMSyncConfig, DMSyncManager
from services.auth_service import AuthService
from services.user_service import UserService
from services.meeting_service import MeetingService
from services.auth_dependencies import require_auth

from models  import Participant, User


# 路由与服务实例
router = APIRouter(prefix="/api/meetings", tags=["Presence"])
presence_manager = ConnectionManager()

# 对外暴露的依赖注入函数
db_config = DMSyncConfig()
db_manager = DMSyncManager(db_config)
get_db = db_manager.get_session_dependency  # 同步会话依赖
get_async_db = db_manager.get_session_dependency



auth_service = AuthService()
user_service = UserService()
meeting_service = MeetingService()


def _extract_ws_token(websocket: WebSocket) -> Optional[str]:
    """从 WebSocket 连接中提取 token（支持 Authorization: Bearer 和 query 参数 token）"""
    # 优先从头部获取
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    # 其次从 query 参数获取
    token = websocket.query_params.get("token")
    return token


@router.websocket("/ws/meetings/{meeting_id}/presence")
async def presence_ws(websocket: WebSocket, meeting_id: str) -> None:
    """会议在线人员统计：WebSocket 路由（内存版 MVP）
    - 验证 access token
    - 验证用户是会议参与者
    - 记录 presence 连接（用户维度）
    - 心跳处理与断开清理
    - 广播 join/leave 事件
    """
    # 提取并验证 token
    token = _extract_ws_token(websocket)
    if not token:
        await websocket.close(code=1008)
        return

    payload = auth_service.verify_token(token, expected_type="access")
    if not payload:
        await websocket.close(code=1008)
        return

    user_id: str = str(payload.get("sub"))
    if not user_id:
        await websocket.close(code=1008)
        return

    # 数据库校验：用户属于会议参与者
    db: Session = db_manager.sync_session_factory()
    try:
        participant = db.query(Participant).filter(
            Participant.meeting_id == meeting_id,
            Participant.user_code == user_id
        ).first()
        if not participant:
            await websocket.close(code=1008)
            return

        # 获取用户基础信息用于广播元数据
        user: Optional[User] = await user_service.get_user_by_id(db, user_id)
        user_name = user.name if user else participant.name
        user_role = user.user_role if user else "participant"

        metadata: Dict[str, Any] = {
            "name": user_name,
            "role": user_role
        }

        # 建立 presence 连接（内部会 accept）
        await presence_manager.connect_presence(websocket, meeting_id, user_id, metadata)

        # 广播 join 事件
        await presence_manager.broadcast_presence_event(meeting_id, {
            "type": "presence.join",
            "meeting_id": meeting_id,
            "user": {"id": user_id, "name": user_name, "role": user_role},
            "online_count": presence_manager.get_online_count(meeting_id)
        })

        # 主循环：处理心跳/快照请求
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            event: Dict[str, Any]
            try:
                event = json.loads(raw)
            except Exception:
                # 非JSON按心跳处理
                event = {"type": "heartbeat"}

            etype = (event.get("type") or "").lower()
            if etype == "heartbeat":
                presence_manager.heartbeat(meeting_id, user_id)
                ack = {
                    "type": "presence.heartbeat_ack",
                    "meeting_id": meeting_id,
                    "user_id": user_id,
                    "ts": datetime.utcnow().isoformat() + "Z"
                }
                # 个人回执
                try:
                    await websocket.send_text(json.dumps(ack, ensure_ascii=False))
                except Exception:
                    pass
            elif etype in ("snapshot", "snapshot.request"):
                snapshot = {
                    "type": "presence.snapshot",
                    "meeting_id": meeting_id,
                    "online_count": presence_manager.get_online_count(meeting_id),
                    "users": presence_manager.get_online_users(meeting_id)
                }
                try:
                    await websocket.send_text(json.dumps(snapshot, ensure_ascii=False))
                except Exception:
                    pass
            else:
                # 忽略未知事件类型
                pass

    finally:
        # 断开清理与 leave 广播
        try:
            presence_manager.disconnect_presence(websocket, meeting_id, user_id)
        except Exception:
            # 防御性处理，避免断开过程异常
            pass

        # 若用户已无其他连接，则广播离线事件
        still_online = (
            meeting_id in presence_manager.meeting_user_sockets and
            user_id in presence_manager.meeting_user_sockets.get(meeting_id, {})
        )

        if not still_online:
            # 获取用户元信息（可能已被清理，回退简单结构）
            meta_map = presence_manager.meeting_user_metadata.get(meeting_id, {})
            meta = meta_map.get(user_id, {})
            user_name = meta.get("name") or participant.name if 'participant' in locals() and participant else None
            user_role = meta.get("role") or "participant"
            try:
                await presence_manager.broadcast_presence_event(meeting_id, {
                    "type": "presence.leave",
                    "meeting_id": meeting_id,
                    "user": {"id": user_id, "name": user_name, "role": user_role},
                    "online_count": presence_manager.get_online_count(meeting_id)
                })
            except Exception:
                pass


@router.get("/{meeting_id}/online-count")
async def get_online_count(
    meeting_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """查询会议在线人员数量（需要访问权限）"""
    user_id = str(current_user.id)
    # 验证用户对会议的访问权限
    meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or access denied")
    count = presence_manager.get_online_count(meeting_id)
    return {"meeting_id": meeting_id, "online_count": count}


@router.get("/{meeting_id}/online-users")
async def get_online_users(
    meeting_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """查询会议在线用户列表（需要访问权限）"""
    user_id = str(current_user.id)
    meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or access denied")
    users = presence_manager.get_online_users(meeting_id)
    return {"meeting_id": meeting_id, "online_users": users}
