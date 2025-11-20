from typing import Dict
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
import json

# WebSocket connection manager
class ConnectionManager(object):
    def __init__(self) -> None:
        # meeting_id -> List[WebSocket]
        self.active_connections: dict[str, list[WebSocket]] = {}
        # Presence: meeting_id -> user_id -> set[WebSocket]
        self.meeting_user_sockets: dict[str, dict[str, set[WebSocket]]] = {}
        # Presence last seen: meeting_id -> user_id -> datetime
        self.meeting_user_last_seen: dict[str, dict[str, datetime]] = {}
        # Presence metadata: meeting_id -> user_id -> dict
        self.meeting_user_metadata: dict[str, dict[str, dict]] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str) -> None:
        await websocket.accept()
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = []
        self.active_connections[meeting_id].append(websocket)

    async def connect_presence(self,
                               websocket: WebSocket,
                               meeting_id: str,
                               user_id: str,
                               metadata: Dict | None = None) -> None:
        """Accept and register a presence connection for a specific user within a meeting.
        - Adds websocket to meeting broadcast list
        - Tracks user-level sockets and metadata
        - Initializes last_seen
        """
        await self.connect(websocket, meeting_id)

        # Initialize maps
        if meeting_id not in self.meeting_user_sockets:
            self.meeting_user_sockets[meeting_id] = {}
        if meeting_id not in self.meeting_user_last_seen:
            self.meeting_user_last_seen[meeting_id] = {}
        if meeting_id not in self.meeting_user_metadata:
            self.meeting_user_metadata[meeting_id] = {}

        # Add socket to user's set
        user_sockets = self.meeting_user_sockets[meeting_id].get(user_id)
        if not user_sockets:
            user_sockets = set()
            self.meeting_user_sockets[meeting_id][user_id] = user_sockets
        user_sockets.add(websocket)

        # Update metadata and last_seen
        if metadata is not None:
            self.meeting_user_metadata[meeting_id][user_id] = metadata
        self.meeting_user_last_seen[meeting_id][user_id] = datetime.now(timezone.utc)

    def disconnect(self, websocket: WebSocket, meeting_id: str)-> None:
        if meeting_id in self.active_connections:
            self.active_connections[meeting_id].remove(websocket)
            if not self.active_connections[meeting_id]:
                del self.active_connections[meeting_id]

    def disconnect_presence(self, websocket: WebSocket, meeting_id: str, user_id: str) -> None:
        """Remove a presence connection for the given user.
        - Removes websocket from user sockets set
        - If user has no remaining sockets, clears metadata/last_seen
        - Also removes websocket from meeting broadcast list
        """
        # Remove from meeting broadcast list
        self.disconnect(websocket, meeting_id)

        # Remove from user sockets
        sockets_map = self.meeting_user_sockets.get(meeting_id)
        if sockets_map and user_id in sockets_map:
            sockets = sockets_map[user_id]
            if websocket in sockets:
                try:
                    sockets.remove(websocket)
                except KeyError:
                    pass
            # If user has no sockets left, cleanup
            if not sockets:
                del sockets_map[user_id]
                # Cleanup last_seen and metadata
                last_seen_map = self.meeting_user_last_seen.get(meeting_id)
                if last_seen_map and user_id in last_seen_map:
                    del last_seen_map[user_id]
                meta_map = self.meeting_user_metadata.get(meeting_id)
                if meta_map and user_id in meta_map:
                    del meta_map[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket)->None:
        """
        向指定WebSocket连接发送个人消息
        参数:
            message: 要发送的消息内容
            websocket: 目标WebSocket连接
        异常:
            ValueError: 当websocket参数无效时抛出
            WebSocketDisconnect: 当连接已断开时抛出
        """
        if not isinstance(websocket, WebSocket):
            raise ValueError("Invalid WebSocket connection")

        if not message:
            return  # 空消息不做处理
        try:
            await websocket.send_text(message)
        except WebSocketDisconnect:
            # 连接已断开，抛出异常让上层处理
            raise
        except Exception as e:
            # 记录其他异常日志
            print(f"Failed to send message: {str(e)}")
            raise

    async def broadcast(self, message: str, meeting_id: str) -> None:
        """
        向指定会议中的所有WebSocket连接广播消息
        参数:
            message: 要广播的消息内容
            meeting_id: 目标会议ID
        异常:
            ValueError: 当message或meeting_id无效时抛出
        """
        if not message or not isinstance(message, str):
            raise ValueError("Message must be a non-empty string")

        if not meeting_id or not isinstance(meeting_id, str):
            raise ValueError("Meeting ID must be a non-empty string")

        if meeting_id not in self.active_connections:
            return
        disconnected_sockets = []
        for connection in self.active_connections[meeting_id]:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                # 记录断开连接以便后续移除
                disconnected_sockets.append(connection)
                print(f"WebSocket disconnected during broadcast for meeting {meeting_id}")
            except Exception as e:
                # 记录其他发送错误
                print(f"Failed to send message to WebSocket in meeting {meeting_id}: {str(e)}")

        # 移除所有断开连接的socket
        for socket in disconnected_sockets:
            self.disconnect(socket, meeting_id)

    async def broadcast_json(self, data: dict, meeting_id: str) -> None:
        """Broadcast JSON to all sockets in the meeting."""
        if not isinstance(data, dict):
            raise ValueError("Data must be a dict")
        if meeting_id not in self.active_connections:
            return
        disconnected_sockets = []
        message = json.dumps(data, ensure_ascii=False)
        for connection in self.active_connections[meeting_id]:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                disconnected_sockets.append(connection)
            except Exception as e:
                print(f"Failed to send JSON to WebSocket in meeting {meeting_id}: {str(e)}")
        for socket in disconnected_sockets:
            self.disconnect(socket, meeting_id)

    def heartbeat(self, meeting_id: str, user_id: str) -> None:
        """Update last seen for user in meeting."""
        if meeting_id not in self.meeting_user_last_seen:
            self.meeting_user_last_seen[meeting_id] = {}
        self.meeting_user_last_seen[meeting_id][user_id] = datetime.now(timezone.utc)

    def get_online_count(self, meeting_id: str) -> int:
        """Get number of distinct online users in a meeting."""
        sockets_map = self.meeting_user_sockets.get(meeting_id)
        return len(sockets_map) if sockets_map else 0

    def get_online_users(self, meeting_id: str) -> list[dict]:
        """Get online users metadata and last_seen for a meeting."""
        sockets_map = self.meeting_user_sockets.get(meeting_id) or {}
        last_seen_map = self.meeting_user_last_seen.get(meeting_id) or {}
        meta_map = self.meeting_user_metadata.get(meeting_id) or {}
        users: list[dict] = []
        for user_id in sockets_map.keys():
            users.append({
                "id": user_id,
                "last_active": (last_seen_map.get(user_id).isoformat() if last_seen_map.get(user_id) else None),
                "metadata": meta_map.get(user_id) or {}
            })
        return users

    async def broadcast_presence_event(self, meeting_id: str, event: dict) -> None:
        """Broadcast a presence event (join/leave/snapshot) to the meeting room."""
        await self.broadcast_json(event, meeting_id)
