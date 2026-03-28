import asyncio
import logging
from typing import Optional
from fastapi import WebSocket
from app.session.state import ConversationSession, SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}
        self._websockets: dict[str, WebSocket] = {}

    def create(self, ws_id: str, ws: WebSocket) -> ConversationSession:
        session = ConversationSession(ws_id=ws_id)
        self._sessions[ws_id] = session
        self._websockets[ws_id] = ws
        return session

    def get(self, ws_id: str) -> Optional[ConversationSession]:
        return self._sessions.get(ws_id)

    def get_ws(self, ws_id: str) -> Optional[WebSocket]:
        return self._websockets.get(ws_id)

    def remove(self, ws_id: str):
        self._sessions.pop(ws_id, None)
        self._websockets.pop(ws_id, None)

    async def interrupt_session(self, ws_id: str):
        session = self.get(ws_id)
        if not session:
            return
        session.interrupt_event.set()
        # Drain TTS queue
        while not session.tts_queue.empty():
            try:
                session.tts_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        if session.tts_task and not session.tts_task.done():
            session.tts_task.cancel()
        if session.llm_task and not session.llm_task.done():
            session.llm_task.cancel()
        session.interrupt_event.clear()   # C6: clear after drain so next turn starts clean
        session.state = SessionState.INTERRUPTED

    async def broadcast(self, message: dict):
        """Send JSON message to every connected WebSocket."""
        dead = []
        for ws_id, ws in list(self._websockets.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws_id)
        for ws_id in dead:
            self.remove(ws_id)

    def active_count(self) -> int:
        return len(self._sessions)


session_manager = SessionManager()
