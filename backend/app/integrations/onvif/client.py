"""Cliente ONVIF PullPoint para Hanwha Wisenet XNO-6120R (cruce de línea IVA).

Action=Left → entrada, Action=Right → salida; solo cuenta State=1/true.
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# zeep es síncrono: cada cámara ocupa un hilo mientras espera PullMessages.
_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="onvif")

_EVENTS_NS = "http://www.onvif.org/ver10/events/wsdl"
_SCHEMA_NS = "http://www.onvif.org/ver10/schema"
_SUBSCRIPTION_MANAGER_BINDING = f"{{{_EVENTS_NS}}}SubscriptionManagerBinding"


@dataclass
class CountData:
    """Nuevos cruces recibidos en un ciclo."""
    in_count: int
    out_count: int


class CameraConnectionError(Exception):
    """Fallo de red, autenticación o protocolo al hablar con la cámara."""


def parse_line_crossing(notifications: Iterable[Any]) -> tuple[int, int]:
    """Cuenta entradas/salidas en una lista de NotificationMessage ONVIF (sin red)."""
    in_count = out_count = 0

    for msg in notifications:
        try:
            message = msg.Message
            prop_op = getattr(message, "PropertyOperation", None)
            if prop_op is None and hasattr(message, "get"):
                prop_op = message.get("PropertyOperation")
            if prop_op == "Initialized":
                continue

            msg_el = getattr(message, "_value_1", None)
            if msg_el is None:
                continue
            if prop_op is None:
                prop_op = msg_el.get("PropertyOperation")
                if prop_op == "Initialized":
                    continue

            data_el = msg_el.find(f"{{{_SCHEMA_NS}}}Data")
            if data_el is None:
                continue

            state = None
            action = ""
            for item in data_el:
                name = item.get("Name", "").lower()
                value = item.get("Value", "").lower()
                if name == "state":
                    state = value
                elif name == "action":
                    action = value

            if state not in ("1", "true"):
                continue

            if "left" in action:
                in_count += 1
            elif "right" in action:
                out_count += 1
            else:
                in_count += 1  # Sin campo Action → asumir entrada
        except Exception as exc:  # un mensaje raro no debe tumbar el lote
            logger.debug("Mensaje ONVIF no interpretable: %s", exc)

    return in_count, out_count


def _make_camera_class():
    """Importa onvif-zeep en diferido y define la subclase sin auto-suscripción.

    ONVIFCamera() crea una suscripción sin TTL al construirse; cada reconexión
    dejaría huérfanas y la cámara acabaría rechazando nuevas.
    """
    from onvif import ONVIFCamera
    from onvif.definition import SERVICES

    class _ONVIFCameraNoAutoSubscribe(ONVIFCamera):
        def update_xaddrs(self):  # noqa: D401 — réplica de la base sin el Subscribe
            self.dt_diff = None
            self.devicemgmt = self.create_devicemgmt_service()
            if self.adjust_time:
                import datetime as dt
                cdate = self.devicemgmt.GetSystemDateAndTime().UTCDateTime
                cam_date = dt.datetime(
                    cdate.Date.Year, cdate.Date.Month, cdate.Date.Day,
                    cdate.Time.Hour, cdate.Time.Minute, cdate.Time.Second,
                )
                self.dt_diff = cam_date - dt.datetime.utcnow()
                self.devicemgmt.dt_diff = self.dt_diff
                self.devicemgmt = self.create_devicemgmt_service()

            self.xaddrs = {}
            capabilities = self.devicemgmt.GetCapabilities({"Category": "All"})
            for name in capabilities:
                capability = capabilities[name]
                if name.lower() in SERVICES and capability is not None:
                    self.xaddrs[SERVICES[name.lower()]["ns"]] = capability["XAddr"]

    return _ONVIFCameraNoAutoSubscribe


class OnvifCameraClient:
    """Métodos públicos async; el trabajo zeep (síncrono) corre en el executor."""

    def __init__(
        self,
        ip: str,
        user: str,
        password: str,
        *,
        port: int = 80,
        timeout: int = 8,
        pull_timeout: int = 3,
        subscription_ttl: int = 120,
        unsubscribe: bool = False,
    ) -> None:
        self._unsubscribe = unsubscribe
        self.ip = ip
        self._user = user
        self._password = password
        self._port = port
        self._timeout = timeout
        self._pull_timeout = pull_timeout
        self._ttl = subscription_ttl

        self._pullpoint = None
        self._subscription = None
        self._renewed_at = 0.0
        self._renew_supported = True

    @property
    def connected(self) -> bool:
        return self._pullpoint is not None

    async def connect(self) -> None:
        await self._run(self._connect_sync)

    async def pull(self) -> CountData:
        return await self._run(self._pull_sync)

    async def close(self) -> None:
        await self._run(self._close_sync)

    @staticmethod
    async def _run(fn):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, fn)

    def _transport(self, operation_timeout: int):
        from zeep.transports import Transport
        return Transport(timeout=self._timeout, operation_timeout=operation_timeout)

    def _connect_sync(self) -> None:
        self._close_sync()
        try:
            camera_cls = _make_camera_class()
        except ImportError as exc:
            raise CameraConnectionError("onvif-zeep no está instalado") from exc

        logger.info("Conectando ONVIF %s:%d...", self.ip, self._port)
        try:
            # Timeout (connect, read): conectar falla rápido y la lectura cubre el
            # long-poll de PullMessages. adjust_time evita NotAuthorized por desfase de reloj.
            cam = camera_cls(
                self.ip, self._port, self._user, self._password,
                adjust_time=True,
                transport=self._transport((self._timeout, self._timeout + self._pull_timeout)),
            )
            events = cam.create_events_service()
            _log_max_pullpoints(events, self.ip)
            sub = events.CreatePullPointSubscription(
                {"InitialTerminationTime": f"PT{self._ttl}S"}
            )
            address = sub.SubscriptionReference.Address._value_1
            cam.xaddrs[f"{_EVENTS_NS}/PullPointSubscription"] = address
            pullpoint = cam.create_pullpoint_service()
            subscription = pullpoint.zeep_client.create_service(
                _SUBSCRIPTION_MANAGER_BINDING, address
            )

            # Descartar el estado inicial ("Initialized") de las reglas IVA
            initial = pullpoint.PullMessages({"MessageLimit": 100, "Timeout": "PT1S"})
            n_init = len(initial.NotificationMessage or [])
        except Exception as exc:
            raise CameraConnectionError(_describe(exc)) from exc

        self._pullpoint = pullpoint
        self._subscription = subscription
        self._renewed_at = time.monotonic()
        logger.info("ONVIF activo en %s (descartados %d mensajes iniciales).", self.ip, n_init)

    def _pull_sync(self) -> CountData:
        if self._pullpoint is None:
            raise CameraConnectionError("sin suscripción activa")

        self._keep_subscription_alive()

        try:
            messages = self._pullpoint.PullMessages({
                "MessageLimit": 100,
                "Timeout": f"PT{self._pull_timeout}S",
            })
        except Exception as exc:
            # Se descarta la suscripción local; el poller reconecta con una nueva
            self._close_sync()
            raise CameraConnectionError(_describe(exc)) from exc

        new_in, new_out = parse_line_crossing(messages.NotificationMessage or [])
        if new_in or new_out:
            logger.info("Cámara %s: +%d IN +%d OUT", self.ip, new_in, new_out)
        return CountData(new_in, new_out)

    def _keep_subscription_alive(self) -> None:
        """Renueva a mitad del TTL; si la cámara no acepta Renew, resuscribe antes de que venza."""
        age = time.monotonic() - self._renewed_at
        if self._renew_supported and age >= self._ttl / 2:
            try:
                self._subscription.Renew(TerminationTime=f"PT{self._ttl}S")
                self._renewed_at = time.monotonic()
                return
            except Exception as exc:
                self._renew_supported = False
                logger.warning(
                    "La cámara %s no aceptó Renew (%s); se resuscribirá antes de cada vencimiento.",
                    self.ip, _describe(exc),
                )
        if not self._renew_supported and age >= self._ttl - self._pull_timeout - 10:
            self._connect_sync()

    def _close_sync(self) -> None:
        subscription = self._subscription
        self._pullpoint = None
        self._subscription = None
        # Unsubscribe desactivado por defecto: en algunas cámaras cancela TODAS las
        # suscripciones (incluidas las de un NVR); con TTL corto la abandonada vence sola.
        if subscription is None or not self._unsubscribe:
            return
        try:
            subscription.Unsubscribe()
            logger.info("Suscripción ONVIF liberada en %s.", self.ip)
        except Exception as exc:
            logger.debug("Unsubscribe falló en %s: %s", self.ip, exc)


def _log_max_pullpoints(events, ip: str) -> None:
    """Diagnóstico: cuántas suscripciones PullPoint simultáneas admite la cámara."""
    try:
        caps = events.GetServiceCapabilities()
        logger.info("Cámara %s admite MaxPullPoints=%s.", ip, getattr(caps, "MaxPullPoints", "?"))
    except Exception as exc:
        logger.debug("GetServiceCapabilities no disponible en %s: %s", ip, exc)


def _describe(exc: Exception) -> str:
    """Mensaje corto y legible para mostrar en el dashboard."""
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "La cámara no responde (timeout)"
    if "refused" in lowered:
        return "Conexión rechazada (¿puerto ONVIF correcto?)"
    if "no route" in lowered or "unreachable" in lowered or "name or service" in lowered:
        return "Cámara inalcanzable en la red"
    if "notauthorized" in lowered or "not authorized" in lowered or "401" in lowered:
        return "Credenciales rechazadas por la cámara"
    return text[:200]
