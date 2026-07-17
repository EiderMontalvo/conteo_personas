"""
app/websockets/connection_manager.py
--------------------------------------
ConnectionManager — única fuente de verdad para conexiones WebSocket activas.
Extrae la lógica que antes vivía acoplada en poller.py.

Uso:
    from app.websockets.connection_manager import ws_manager

    await ws_manager.connect(websocket)
    await ws_manager.broadcast({"type": "count_update", "payload": {...}})
    ws_manager.disconnect(websocket)
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gestiona las conexiones WebSocket activas y hace broadcast a todas."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    @property
    def count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Acepta y registra una nueva conexión WebSocket."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WS conectado. Activos: %d", self.count)

    def disconnect(self, websocket: WebSocket) -> None:
        """Elimina una conexión del registro (no hace close)."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WS desconectado. Activos: %d", self.count)

    async def broadcast(self, message: dict) -> None:
        """
        Envía un mensaje JSON a todos los clientes conectados.
        Elimina silenciosamente las conexiones muertas.
        """
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Singleton compartido por toda la aplicación
ws_manager = ConnectionManager()
