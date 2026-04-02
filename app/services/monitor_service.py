import asyncio
import logging
import os

import httpx
import psutil

from app.session.manager import session_manager
from config import settings

logger = logging.getLogger(__name__)

HISTORY_LEN = 30


class MonitorService:
    def __init__(self):
        self.cpu_history: list[float] = [0.0] * HISTORY_LEN
        self.ram_history: list[float] = [0.0] * HISTORY_LEN
        self._proc = psutil.Process(os.getpid())
        self._proc.cpu_percent()  # discard first reading
        psutil.cpu_percent()  # discard first dummy reading (always 0.0)

    async def run_loop(self):
        """Background asyncio task — poll every second, broadcast to all sessions."""
        while True:
            await asyncio.sleep(1.0)
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Monitor tick error: {e}")

    async def _tick(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        self.cpu_history.append(cpu)
        self.cpu_history.pop(0)
        self.ram_history.append(mem.percent)
        self.ram_history.pop(0)

        # Process-specific metrics
        try:
            proc_mem_mb = round(self._proc.memory_info().rss / 1e6, 1)
            proc_cpu = round(self._proc.cpu_percent(), 1)
        except Exception:
            proc_mem_mb = 0.0
            proc_cpu = 0.0

        ollama_status = await self._ping_ollama()

        await session_manager.broadcast(
            {
                "type": "monitor_status",
                "cpu_percent": round(cpu, 1),
                "ram_percent": round(mem.percent, 1),
                "ram_used_gb": round(mem.used / 1e9, 2),
                "ram_total_gb": round(mem.total / 1e9, 2),
                "proc_mem_mb": proc_mem_mb,
                "proc_cpu": proc_cpu,
                "ollama_status": ollama_status,
                "cpu_history": list(self.cpu_history),
                "ram_history": list(self.ram_history),
            }
        )

    async def _ping_ollama(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                r = await client.get(f"{settings.ollama_host}/api/tags")
                return "connected" if r.status_code == 200 else "error"
        except Exception:
            return "disconnected"


monitor_service = MonitorService()
