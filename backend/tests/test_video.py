"""Proxy de video: MJPEG nativo, respaldo con snapshots y errores legibles (cámara simulada)."""
import httpx
import pytest

from app.integrations import video

JPEG = b"\xff\xd8fake-jpeg\xff\xd9"


def fake_camera(monkeypatch, *, stream_ok=True, snapshot_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        sub = request.url.params.get("msubmenu")
        if sub == "stream":
            if stream_ok:
                return httpx.Response(200, headers={"content-type": "multipart/x-mixed-replace; boundary=cam"},
                                      content=b"--cam\r\nContent-Type: image/jpeg\r\n\r\n" + JPEG)
            return httpx.Response(404)
        if sub == "snapshot":
            if snapshot_status == 200:
                return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=JPEG)
            return httpx.Response(snapshot_status)
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(video, "_client_factory", lambda **kw: httpx.AsyncClient(transport=transport, **kw))


@pytest.mark.asyncio
async def test_snapshot_returns_jpeg(monkeypatch):
    fake_camera(monkeypatch)
    assert await video.fetch_snapshot("10.0.0.9") == JPEG


@pytest.mark.asyncio
async def test_snapshot_bad_credentials_is_readable(monkeypatch):
    fake_camera(monkeypatch, snapshot_status=401)
    with pytest.raises(video.VideoUnavailable, match="Credenciales"):
        await video.fetch_snapshot("10.0.0.9")


@pytest.mark.asyncio
async def test_native_mjpeg_is_passed_through(monkeypatch):
    fake_camera(monkeypatch)
    ctype, body = await video.open_mjpeg("10.0.0.9")
    assert ctype.startswith("multipart/x-mixed-replace; boundary=cam")
    data = b"".join([chunk async for chunk in body])
    assert JPEG in data


@pytest.mark.asyncio
async def test_falls_back_to_snapshots(monkeypatch):
    fake_camera(monkeypatch, stream_ok=False)
    ctype, body = await video.open_mjpeg("10.0.0.9")
    assert ctype == f"multipart/x-mixed-replace; boundary={video.BOUNDARY}"
    first = await body.__anext__()
    assert first.startswith(b"--frame\r\nContent-Type: image/jpeg") and JPEG in first
    await body.aclose()


@pytest.mark.asyncio
async def test_no_image_at_all_raises(monkeypatch):
    fake_camera(monkeypatch, stream_ok=False, snapshot_status=500)
    with pytest.raises(video.VideoUnavailable):
        await video.open_mjpeg("10.0.0.9")
