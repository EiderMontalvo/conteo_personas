"""CameraPoller: reconexión con backoff, estados y no bloquearse ante fallos."""
import asyncio
from types import SimpleNamespace

import pytest

from app.integrations.onvif import event_listener as el
from app.integrations.onvif.client import CameraConnectionError, CountData


class FlakyClient:
    """Falla `fail_connects` veces al conectar y luego entrega cruces."""

    def __init__(self, fail_connects=2, drop_after=None):
        self.ip = "10.0.0.9"
        self.connected = False
        self.connect_calls = 0
        self.closed = 0
        self._fail_connects = fail_connects
        self._drop_after = drop_after
        self._pulls = 0

    async def connect(self):
        self.connect_calls += 1
        if self.connect_calls <= self._fail_connects:
            raise CameraConnectionError("La cámara no responde (timeout)")
        self.connected = True

    async def pull(self):
        await asyncio.sleep(0.01)
        self._pulls += 1
        if self._drop_after and self._pulls == self._drop_after:
            self.connected = False
            raise CameraConnectionError("Cámara inalcanzable en la red")
        return CountData(1, 0)

    async def close(self):
        self.closed += 1
        self.connected = False


@pytest.fixture()
def fast(monkeypatch):
    """Backoff instantáneo, sin BD real ni WebSocket."""
    monkeypatch.setattr(el.CameraPoller, "_backoff_delay", lambda self: 0.01)
    processed = []

    async def fake_process(**kw):
        processed.append((kw["raw_in"], kw["raw_out"]))

    monkeypatch.setattr(el.counting_service, "process", fake_process)
    broadcasts = []

    async def fake_broadcast(msg):
        broadcasts.append(msg)

    monkeypatch.setattr(el.ws_manager, "broadcast", fake_broadcast)
    return SimpleNamespace(processed=processed, broadcasts=broadcasts)


def _camera():
    return SimpleNamespace(
        camera_id=0, name="Cam", ip_address="10.0.0.9", role="both", zone=None, max_capacity=100,
    )


async def _wait_for(cond, timeout=2.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condición no alcanzada")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_reconnects_after_failures_and_counts(fast):
    client = FlakyClient(fail_connects=2)
    poller = el.CameraPoller(_camera(), client=client)
    poller.start()
    await _wait_for(lambda: len(fast.processed) >= 2)

    assert client.connect_calls == 3
    assert poller.state == el.CONNECTED
    assert poller.failures == 0  # se reinicia al conectar
    states = [m["payload"]["state"] for m in fast.broadcasts if m["type"] == "camera_status"]
    assert states[:2] == [el.CONNECTING, el.RECONNECTING]
    assert el.CONNECTED in states

    await poller.stop()
    assert poller.state == el.STOPPED
    assert client.closed >= 1


@pytest.mark.asyncio
async def test_recovers_when_connection_drops(fast):
    client = FlakyClient(fail_connects=0, drop_after=3)
    poller = el.CameraPoller(_camera(), client=client)
    poller.start()
    await _wait_for(lambda: client.connect_calls >= 2 and len(fast.processed) >= 4)
    assert poller.state == el.CONNECTED
    await poller.stop()


@pytest.mark.asyncio
async def test_failure_exposes_error_in_snapshot(fast):
    client = FlakyClient(fail_connects=10**6)
    poller = el.CameraPoller(_camera(), client=client)
    poller.start()
    await _wait_for(lambda: poller.failures >= 3)

    snap = poller.snapshot()
    assert snap["state"] == el.RECONNECTING
    assert "timeout" in snap["last_error"]
    assert snap["next_retry_at"] is not None
    await poller.stop()


def test_backoff_grows_and_is_capped(monkeypatch):
    monkeypatch.setattr(el.settings, "reconnect_max_delay", 60)
    poller = el.CameraPoller(_camera(), client=FlakyClient())
    delays = []
    for failures in (1, 2, 3, 6, 20):
        poller.failures = failures
        delays.append(poller._backoff_delay())
    assert delays == [2, 4, 8, 60, 60]
