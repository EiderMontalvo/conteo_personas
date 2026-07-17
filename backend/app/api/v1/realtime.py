"""
app/api/v1/realtime.py
-----------------------
WebSocket para datos en tiempo real.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websockets.connection_manager import ws_manager

router = APIRouter(tags=["Tiempo Real"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """
    Stream WebSocket en tiempo real.
    El PollerPool hace broadcast aquí cada vez que detecta un cruce de línea.

    Formato de mensaje:
    {
      "type": "count_update",
      "payload": {
        "camera_id": 0,
        "camera_name": "Puerta Principal",
        "group": null,
        "timestamp": "2026-07-17T10:00:00+00:00",
        "in_count": 1,
        "out_count": 0,
        "accum_in": 5,
        "accum_out": 3
      }
    }
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantener la conexión activa
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
