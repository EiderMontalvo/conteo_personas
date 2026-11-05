"""Cliente ONVIF: parseo de eventos y ciclo de vida de la suscripción (sin red)."""
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from app.integrations.onvif import client as client_mod
from app.integrations.onvif.client import (
    CameraConnectionError,
    OnvifCameraClient,
    parse_line_crossing,
)

NS = "http://www.onvif.org/ver10/schema"


def _event(state="1", action="Left", prop_op="Changed"):
    msg = ET.Element(f"{{{NS}}}Message", {"PropertyOperation": prop_op})
    data = ET.SubElement(msg, f"{{{NS}}}Data")
    ET.SubElement(data, f"{{{NS}}}SimpleItem", {"Name": "State", "Value": state})
    if action is not None:
        ET.SubElement(data, f"{{{NS}}}SimpleItem", {"Name": "Action", "Value": action})
    return SimpleNamespace(Message=SimpleNamespace(_value_1=msg))


class TestParseLineCrossing:
    def test_left_is_in_right_is_out(self):
        assert parse_line_crossing([_event(action="Left"), _event(action="Right")]) == (1, 1)

    def test_end_of_crossing_is_ignored(self):
        assert parse_line_crossing([_event(state="0"), _event(state="false")]) == (0, 0)

    def test_true_state_counts(self):
        assert parse_line_crossing([_event(state="true", action="Right")]) == (0, 1)

    def test_initialized_messages_are_ignored(self):
        assert parse_line_crossing([_event(prop_op="Initialized")]) == (0, 0)

    def test_missing_action_counts_as_in(self):
        assert parse_line_crossing([_event(action=None)]) == (1, 0)

    def test_malformed_message_does_not_break_batch(self):
        broken = SimpleNamespace(Message=None)
        assert parse_line_crossing([broken, _event()]) == (1, 0)


# Ciclo de vida de la suscripción.

class FakeSubscription:
    def __init__(self, renew_ok=True):
        self.renew_calls = 0
        self.unsubscribe_calls = 0
        self._renew_ok = renew_ok

    def Renew(self, **_):
        self.renew_calls += 1
        if not self._renew_ok:
            raise RuntimeError("ActionNotSupported")

    def Unsubscribe(self):
        self.unsubscribe_calls += 1


class FakePullPoint:
    def __init__(self, batches=None, fail=False):
        self._batches = list(batches or [])
        self._fail = fail

    def PullMessages(self, _params):
        if self._fail:
            raise ConnectionError("Connection to 10.0.0.9 timed out")
        msgs = self._batches.pop(0) if self._batches else []
        return SimpleNamespace(NotificationMessage=msgs)


def _connected_client(monkeypatch, *, pullpoint, subscription, ttl=120, unsubscribe=False):
    c = OnvifCameraClient("10.0.0.9", "u", "p", subscription_ttl=ttl, unsubscribe=unsubscribe)
    c._pullpoint = pullpoint
    c._subscription = subscription
    clock = {"t": 1000.0}
    monkeypatch.setattr(client_mod.time, "monotonic", lambda: clock["t"])
    c._renewed_at = clock["t"]
    return c, clock


def test_pull_returns_counts(monkeypatch):
    c, _ = _connected_client(
        monkeypatch,
        pullpoint=FakePullPoint([[_event(action="Left"), _event(action="Left")]]),
        subscription=FakeSubscription(),
    )
    data = c._pull_sync()
    assert (data.in_count, data.out_count) == (2, 0)


def test_renews_same_subscription_at_half_ttl(monkeypatch):
    sub = FakeSubscription()
    c, clock = _connected_client(monkeypatch, pullpoint=FakePullPoint(), subscription=sub, ttl=120)

    clock["t"] += 30
    c._pull_sync()
    assert sub.renew_calls == 0

    clock["t"] += 31  # 61s > ttl/2
    c._pull_sync()
    assert sub.renew_calls == 1
    assert c._subscription is sub  # se renueva, no se crea otra


def test_resubscribes_before_expiry_when_renew_unsupported(monkeypatch):
    sub = FakeSubscription(renew_ok=False)
    c, clock = _connected_client(monkeypatch, pullpoint=FakePullPoint(), subscription=sub, ttl=120)
    reconnects = []
    monkeypatch.setattr(c, "_connect_sync", lambda: reconnects.append(1))

    clock["t"] += 61
    c._pull_sync()  # Renew falla → se marca como no soportado, sin reconectar aún
    assert reconnects == []
    assert c.connected

    clock["t"] += 50  # 111s ≥ ttl - pull_timeout - 10
    c._pull_sync()
    assert reconnects == [1]


def test_pull_failure_raises_and_drops_subscription(monkeypatch):
    sub = FakeSubscription()
    c, _ = _connected_client(monkeypatch, pullpoint=FakePullPoint(fail=True), subscription=sub)
    with pytest.raises(CameraConnectionError, match="timeout"):
        c._pull_sync()
    assert not c.connected
    assert sub.unsubscribe_calls == 0  # por defecto no se envía Unsubscribe


def test_unsubscribe_only_when_enabled(monkeypatch):
    sub = FakeSubscription()
    c, _ = _connected_client(monkeypatch, pullpoint=FakePullPoint(), subscription=sub, unsubscribe=True)
    c._close_sync()
    assert sub.unsubscribe_calls == 1


def test_pull_without_connection_raises():
    c = OnvifCameraClient("10.0.0.9", "u", "p")
    with pytest.raises(CameraConnectionError):
        c._pull_sync()


def test_camera_class_does_not_auto_subscribe():
    """La subclase no debe llamar a CreatePullPointSubscription al construirse."""
    cls = client_mod._make_camera_class()
    calls = []

    class FakeDevMgmt:
        def GetCapabilities(self, _):
            return {"Events": {"XAddr": "http://10.0.0.9/onvif/event_service"}}

    cam = cls.__new__(cls)
    cam.adjust_time = False
    cam.create_devicemgmt_service = lambda: FakeDevMgmt()
    cam.create_events_service = lambda: calls.append("events")
    cam.update_xaddrs()

    assert calls == []
    assert cam.xaddrs == {"http://www.onvif.org/ver10/events/wsdl": "http://10.0.0.9/onvif/event_service"}


@pytest.mark.parametrize("raw,expected", [
    ("Connection to 1.2.3.4 timed out", "timeout"),
    ("Connection refused", "rechazada"),
    ("Sender not Authorized", "Credenciales"),
])
def test_error_messages_are_readable(raw, expected):
    assert expected in client_mod._describe(RuntimeError(raw))
