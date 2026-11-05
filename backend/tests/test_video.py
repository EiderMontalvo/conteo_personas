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
async def test_native_mjpeg_is_relayed(monkeypatch):
    fake_camera(monkeypatch)
    ctype, body = await video.open_mjpeg("10.0.0.9")
    assert ctype == f"multipart/x-mixed-replace; boundary={video.BOUNDARY}"
    first = await body.__anext__()
    assert first == video._part(JPEG)
    await body.aclose()


@pytest.mark.asyncio
async def test_native_mjpeg_uses_content_length(monkeypatch):
    # Un 0xFFD9 dentro del JPEG no debe cortar el cuadro si hay Content-Length.
    tricky = b"\xff\xd8abc\xff\xd9def\xff\xd9"

    def handler(request):
        return httpx.Response(200, headers={"content-type": "multipart/x-mixed-replace; boundary=cam"},
                              content=b"--cam\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(tricky)
                              + tricky + b"\r\n--cam\r\n")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(video, "_client_factory", lambda **kw: httpx.AsyncClient(transport=transport, **kw))
    _, body = await video.open_mjpeg("10.0.0.9")
    assert await body.__anext__() == video._part(tricky)
    await body.aclose()


@pytest.mark.asyncio
async def test_native_mjpeg_reconnects_after_drop(monkeypatch):
    calls = {"stream": 0}

    def handler(request):
        calls["stream"] += 1
        if calls["stream"] == 2:
            return httpx.Response(503)  # primer reintento falla
        return httpx.Response(200, headers={"content-type": "multipart/x-mixed-replace; boundary=cam"},
                              content=b"--cam\r\nContent-Type: image/jpeg\r\n\r\n" + JPEG)

    async def no_sleep(_):
        return None

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(video, "_client_factory", lambda **kw: httpx.AsyncClient(transport=transport, **kw))
    monkeypatch.setattr(video.asyncio, "sleep", no_sleep)
    _, body = await video.open_mjpeg("10.0.0.9")
    assert await body.__anext__() == video._part(JPEG)
    # La cámara "cortó": sigue en la misma respuesta tras reconectar.
    assert await body.__anext__() == video._part(JPEG)
    assert calls["stream"] == 3
    await body.aclose()


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


def fake_iva_camera(monkeypatch, *, analytics_status=200):
    analytics = {"VideoAnalysis": [{"Channel": 0, "Lines": [
        {"Line": 1, "Mode": "BothDirections", "Coordinates": [{"x": 801, "y": 429}, {"x": 1658, "y": 435}]},
        {"Line": 2, "Mode": "LeftSide", "Coordinates": [{"x": 5, "y": 5}]},  # incompleta: se omite
    ]}]}
    profiles = (
        "Channel.0.Profile.1.Resolution=1920x1080\n"
        "Channel.0.Profile.4.Resolution=800x448\n"
        "Channel.0.Profile.4.FrameRate=8\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        sub = request.url.params.get("msubmenu")
        if sub == "videoanalysis2":
            if analytics_status != 200:
                return httpx.Response(analytics_status)
            return httpx.Response(200, json=analytics)
        if sub == "videoprofile":
            return httpx.Response(200, text=profiles)
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(video, "_client_factory", lambda **kw: httpx.AsyncClient(transport=transport, **kw))


@pytest.mark.asyncio
async def test_iva_lines_in_sensor_resolution(monkeypatch):
    fake_iva_camera(monkeypatch)
    data = await video.fetch_iva_lines("10.0.0.9")
    assert (data["width"], data["height"]) == (1920, 1080)
    assert data["lines"] == [{"line": 1, "mode": "BothDirections", "points": [[801, 429], [1658, 435]]}]


@pytest.mark.asyncio
async def test_iva_lines_bad_credentials_is_readable(monkeypatch):
    fake_iva_camera(monkeypatch, analytics_status=401)
    with pytest.raises(video.VideoUnavailable, match="Credenciales"):
        await video.fetch_iva_lines("10.0.0.9")
