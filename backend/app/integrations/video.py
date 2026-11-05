"""Video en vivo vía SUNAPI: proxy MJPEG y snapshots, con Digest auth del lado del servidor."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BOUNDARY = "frame"
# Sin cuadros durante este tiempo = stream colgado: se reconecta.
STALL_SECONDS = 10
MAX_RECONNECT_SECONDS = 8

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


def _cgi(ip: str, name: str) -> str:
    return f"http://{ip}:{settings.onvif_port}/stw-cgi/{name}.cgi"


async def fetch_iva_lines(ip: str) -> dict:
    """
    Líneas virtuales del IVA y el tamaño de imagen al que se refieren sus coordenadas
    (Hanwha las da en la resolución máxima del sensor, p. ej. 1920x1080).
    """
    try:
        async with _client_factory(timeout=settings.onvif_timeout) as c:
            va = await c.get(
                _cgi(ip, "eventsources"),
                params={"msubmenu": "videoanalysis2", "action": "view"},
                auth=_auth(),
            )
            prof = await c.get(
                _cgi(ip, "media"),
                params={"msubmenu": "videoprofile", "action": "view"},
                auth=_auth(),
            )
    except httpx.HTTPError as exc:
        raise VideoUnavailable(f"La cámara no responde ({exc.__class__.__name__})") from exc
    if va.status_code == 401:
        raise VideoUnavailable("Credenciales rechazadas por la cámara")
    try:
        channel = (va.json().get("VideoAnalysis") or [{}])[0]
    except ValueError as exc:
        raise VideoUnavailable("La cámara no expone líneas IVA (videoanalysis2)") from exc

    width, height = 1920, 1080
    sizes = [
        tuple(int(n) for n in line.split("=", 1)[1].lower().split("x"))
        for line in prof.text.splitlines()
        if line.endswith(tuple("0123456789")) and ".Resolution=" in line
    ]
    if sizes:
        width, height = max(sizes, key=lambda s: s[0] * s[1])

    lines = [
        {
            "line": item.get("Line"),
            "mode": item.get("Mode"),
            "points": [[p["x"], p["y"]] for p in item.get("Coordinates", [])],
        }
        for item in channel.get("Lines", [])
        if len(item.get("Coordinates", [])) >= 2
    ]
    return {"width": width, "height": height, "lines": lines}


def _part(frame: bytes) -> bytes:
    return (
        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode()
        + frame + b"\r\n"
    )


async def _open_native(client: httpx.AsyncClient, ip: str) -> httpx.Response | None:
    """Abre el MJPEG nativo; None si la cámara responde pero no lo ofrece."""
    params = {"msubmenu": "stream", "action": "view", "Channel": 0}
    if settings.video_profile:
        params["Profile"] = settings.video_profile
    else:
        params["CodecType"] = "MJPEG"
    req = client.build_request("GET", _base(ip), params=params)
    resp = await client.send(req, auth=_auth(), stream=True)
    ctype = resp.headers.get("content-type", "")
    if resp.status_code == 200 and ctype.startswith("multipart/"):
        return resp
    await resp.aclose()
    logger.info("Cámara %s sin MJPEG nativo (%s %s).", ip, resp.status_code, ctype)
    return None


async def _jpeg_frames(resp: httpx.Response) -> AsyncIterator[bytes]:
    """Extrae cada JPEG completo del multipart de la cámara (Content-Length o SOI/EOI)."""
    async def feed() -> AsyncIterator[bytes]:
        if resp.is_stream_consumed:  # ya leída (p. ej. por un transporte de prueba)
            yield resp.content
            return
        async for c in resp.aiter_raw():
            yield c

    buf = b""
    async for chunk in feed():
        buf += chunk
        while True:
            soi = buf.find(b"\xff\xd8")
            if soi < 0:
                buf = buf[-1:]  # conservar un posible 0xFF partido
                break
            header = buf[:soi]
            length = None
            for line in header.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try:
                        length = int(line.split(b":", 1)[1])
                    except ValueError:
                        pass
            if length is not None:
                if len(buf) < soi + length:
                    break
                end = soi + length
            else:
                eoi = buf.find(b"\xff\xd9", soi + 2)
                if eoi < 0:
                    break
                end = eoi + 2
            yield buf[soi:end]
            buf = buf[end:]


async def _relay_native(client: httpx.AsyncClient, ip: str, resp: httpx.Response) -> AsyncIterator[bytes]:
    """
    Reenvía los cuadros con boundary propio. Si la cámara corta la conexión o deja
    de mandar cuadros, reconecta y sigue en la MISMA respuesta: el <img> del
    navegador no avisa cuando un MJPEG se corta y se quedaría congelado.
    """
    delay = 1.0
    try:
        while True:
            if resp is not None:
                try:
                    async for frame in _jpeg_frames(resp):
                        delay = 1.0
                        yield _part(frame)
                    logger.info("MJPEG de %s terminó; reconectando.", ip)
                except httpx.HTTPError as exc:
                    logger.info("MJPEG de %s cortado (%s); reconectando.", ip, exc.__class__.__name__)
                finally:
                    await resp.aclose()
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_SECONDS)
            try:
                resp = await _open_native(client, ip)
            except httpx.HTTPError as exc:
                logger.info("Reconexión MJPEG a %s falló (%s).", ip, exc.__class__.__name__)
                resp = None
    finally:
        await client.aclose()


async def open_mjpeg(ip: str) -> tuple[str, AsyncIterator[bytes]]:
    """
    Devuelve (content-type, iterador de bytes). Intenta el stream MJPEG nativo;
    si la cámara no lo da, arma uno con snapshots seguidos (~2 fps).
    Lanza VideoUnavailable si no hay forma de obtener imagen.
    """
    # read=STALL_SECONDS: si la cámara deja de mandar cuadros sin cerrar, se detecta y se reconecta.
    client = _client_factory(timeout=httpx.Timeout(settings.onvif_timeout, read=STALL_SECONDS))
    try:
        resp = await _open_native(client, ip)
        if resp is not None:
            return f"multipart/x-mixed-replace; boundary={BOUNDARY}", _relay_native(client, ip, resp)
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
                yield _part(frame)
                await asyncio.sleep(0.5)
                try:
                    frame = await fetch_snapshot(ip, client)
                except VideoUnavailable as exc:
                    logger.info("Snapshot falló en %s: %s", ip, exc)
                    return
        finally:
            await client.aclose()

    return f"multipart/x-mixed-replace; boundary={BOUNDARY}", snapshots()
