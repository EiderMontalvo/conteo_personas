"""Video en vivo vía SUNAPI: proxy MJPEG y snapshots, con Digest auth del lado del servidor."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BOUNDARY = "frame"

# Punto de inyección para pruebas (httpx.MockTransport).
_client_factory = httpx.AsyncClient


class VideoUnavailable(Exception):
    """La cámara no entregó imagen (apagada, credenciales, o sin soporte)."""


def _auth() -> httpx.DigestAuth:
    return httpx.DigestAuth(settings.camera_user, settings.camera_pass)


def _base(ip: str) -> str:
    return f"http://{ip}:{settings.onvif_port}/stw-cgi/video.cgi"


async def fetch_snapshot(ip: str, client: httpx.AsyncClient | None = None) -> bytes:
    params = {"msubmenu": "snapshot", "action": "view", "Channel": 0}
    try:
        if client is None:
            async with _client_factory(timeout=settings.onvif_timeout) as c:
                r = await c.get(_base(ip), params=params, auth=_auth())
        else:
            r = await client.get(_base(ip), params=params, auth=_auth())
    except httpx.HTTPError as exc:
        raise VideoUnavailable(f"La cámara no responde ({exc.__class__.__name__})") from exc
    if r.status_code == 401:
        raise VideoUnavailable("Credenciales rechazadas por la cámara")
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise VideoUnavailable(f"La cámara respondió {r.status_code} sin imagen")
    return r.content


async def open_mjpeg(ip: str) -> tuple[str, AsyncIterator[bytes]]:
    """
    Devuelve (content-type, iterador de bytes). Intenta el stream MJPEG nativo;
    si la cámara no lo da, arma uno con snapshots seguidos (~2 fps).
    Lanza VideoUnavailable si no hay forma de obtener imagen.
    """
    client = _client_factory(timeout=httpx.Timeout(settings.onvif_timeout, read=None))
    params = {"msubmenu": "stream", "action": "view", "Channel": 0}
    if settings.video_profile:
        params["Profile"] = settings.video_profile
    else:
        params["CodecType"] = "MJPEG"
    try:
        req = client.build_request("GET", _base(ip), params=params)
        resp = await client.send(req, auth=_auth(), stream=True)
        ctype = resp.headers.get("content-type", "")
        if resp.status_code == 200 and ctype.startswith("multipart/"):
            async def passthrough() -> AsyncIterator[bytes]:
                try:
                    if resp.is_stream_consumed:  # ya leída (p. ej. por un transporte de prueba)
                        yield resp.content
                        return
                    async for chunk in resp.aiter_raw():
                        yield chunk
                finally:
                    await resp.aclose()
                    await client.aclose()
            return ctype, passthrough()
        await resp.aclose()
        logger.info("Cámara %s sin MJPEG nativo (%s %s); se usan snapshots.", ip, resp.status_code, ctype)
    except httpx.HTTPError as exc:
        logger.info("MJPEG no disponible en %s (%s); se prueban snapshots.", ip, exc.__class__.__name__)

    try:
        first = await fetch_snapshot(ip, client)
    except VideoUnavailable:
        await client.aclose()
        raise

    async def snapshots() -> AsyncIterator[bytes]:
        frame = first
        try:
            while True:
                yield (
                    f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode()
                    + frame + b"\r\n"
                )
                await asyncio.sleep(0.5)
                try:
                    frame = await fetch_snapshot(ip, client)
                except VideoUnavailable as exc:
                    logger.info("Snapshot falló en %s: %s", ip, exc)
                    return
        finally:
            await client.aclose()

    return f"multipart/x-mixed-replace; boundary={BOUNDARY}", snapshots()
