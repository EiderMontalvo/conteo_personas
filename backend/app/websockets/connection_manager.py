"""Registro de conexiones WebSocket activas y broadcast a todas ellas."""
from __future__ import annotations

import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    @property
    def count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WS conectado. Activos: %d", self.count)

    def disconnect(self, websocket: WebSocket) -> None:
        """Solo la quita del registro; no cierra el socket."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WS desconectado. Activos: %d", self.count)

    async def broadcast(self, message: dict) -> None:
        """Las conexiones que fallan al enviar se descartan en silencio."""
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()
