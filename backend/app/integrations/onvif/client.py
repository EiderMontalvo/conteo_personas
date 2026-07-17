"""
app/integrations/onvif/client.py
---------------------------------
OnvifCameraClient — cliente ONVIF PullPoint para Hanwha Wisenet XNO-6120R.
Refactor de sunapi.py: ahora recibe parámetros individuales (no CameraConfig)
para poder reinicializarse con nueva IP sin recrear el objeto.

DIAGNÓSTICO CONFIRMADO (debugging exhaustivo):
  - ONVIF PullPoint (zeep): funciona.  TopicSet incluye VideoAnalytics.
  - Action=Left  → ENTRADA  |  Action=Right → SALIDA
  - State=1/true → cruce activo (contar)  |  State=0/false → fin del cruce (ignorar)
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Thread pool compartido por todos los clientes ONVIF (zeep es síncrono)
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="onvif")


@dataclass
class CountData:
    """Resultado de una consulta de conteo: nuevos cruces en este ciclo."""
    in_count: int
    out_count: int


class OnvifCameraClient:
    """
    Cliente ONVIF PullPoint para una cámara.
    Ejecuta el código zeep (síncrono) en un ThreadPoolExecutor.

    Se puede reiniciar con nueva IP llamando a reset(new_ip).
    """

    def __init__(self, ip: str, user: str, password: str, port: int = 80) -> None:
        self._ip = ip
        self._user = user
        self._password = password
        self._port = port
        self._cumulative_in: int = 0
        self._cumulative_out: int = 0
        self._poll_count: int = 0
        self._cam_obj = None
        self._pullpoint = None
        self._event_service = None

    # ── API pública ────────────────────────────────────────────────

    @property
    def ip(self) -> str:
        return self._ip

    def reset(self, new_ip: str) -> None:
        """Reinicia la conexión con una nueva IP (sin recrear el objeto)."""
        logger.info("OnvifCameraClient: reset %s → %s", self._ip, new_ip)
        self._ip = new_ip
        self._cam_obj = None
        self._pullpoint = None
        self._event_service = None
        self._poll_count = 0

    async def get_realtime_count(self) -> Optional[CountData]:
        """
        Ciclo de polling. Ejecuta el código zeep en un thread
        para no bloquear el event loop de FastAPI.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(_executor, self._poll_sync)
        except Exception as exc:
            logger.exception("Error inesperado al consultar cámara %s: %s", self._ip, exc)
            self._cam_obj = None
            self._pullpoint = None
            return None

    # ── Internos ───────────────────────────────────────────────────

    def _poll_sync(self) -> Optional[CountData]:
        """Código síncrono (thread): inicializar, pull messages, parsear."""
        self._poll_count += 1

        try:
            if self._cam_obj is None:
                self._init_onvif()

            if self._pullpoint is None:
                return CountData(self._cumulative_in, self._cumulative_out)

            # Renovar suscripción periódicamente (cada 20 ciclos ≈ 60s)
            if self._poll_count % 20 == 0 and self._event_service is not None:
                try:
                    self._event_service.CreatePullPointSubscription(
                        {"InitialTerminationTime": "PT300S"}
                    )
                except Exception as e:
                    logger.warning("Error renovando suscripción ONVIF %s: %s", self._ip, e)

            # Pull de mensajes
            try:
                messages = self._pullpoint.PullMessages({
                    "MessageLimit": 100,
                    "Timeout": "PT3S",
                })
            except Exception as e:
                logger.warning(
                    "Error PullMessages %s: %s — reiniciando suscripción.", self._ip, e
                )
                self._cam_obj = None
                self._pullpoint = None
                return CountData(self._cumulative_in, self._cumulative_out)

            if not messages.NotificationMessage:
                return CountData(self._cumulative_in, self._cumulative_out)

            new_in, new_out = self._parse_messages(messages.NotificationMessage)
            self._cumulative_in += new_in
            self._cumulative_out += new_out

            if new_in + new_out > 0:
                logger.info(
                    "Cámara %s: +%d IN +%d OUT → Total IN=%d OUT=%d",
                    self._ip, new_in, new_out, self._cumulative_in, self._cumulative_out,
                )
            return CountData(self._cumulative_in, self._cumulative_out)

        except Exception as exc:
            logger.exception("Error en _poll_sync %s: %s", self._ip, exc)
            self._cam_obj = None
            self._pullpoint = None
            return None

    def _init_onvif(self) -> None:
        """Inicializa la conexión ONVIF y crea la suscripción PullPoint."""
        try:
            from onvif import ONVIFCamera
        except ImportError:
            logger.error("onvif-zeep no instalado. Ejecuta: pip install onvif-zeep")
            return

        logger.info("Iniciando conexión ONVIF %s:%d...", self._ip, self._port)
        try:
            cam = ONVIFCamera(self._ip, self._port, self._user, self._password)
            event_service = cam.create_events_service()
            event_service.CreatePullPointSubscription({"InitialTerminationTime": "PT300S"})
            pullpoint = cam.create_pullpoint_service()

            # Descartar mensajes iniciales "Initialized"
            init_msgs = pullpoint.PullMessages({"MessageLimit": 100, "Timeout": "PT1S"})
            n_init = len(init_msgs.NotificationMessage) if init_msgs.NotificationMessage else 0
            logger.info(
                "ONVIF activo en %s. Mensajes iniciales descartados: %d.", self._ip, n_init
            )

            self._cam_obj = cam
            self._event_service = event_service
            self._pullpoint = pullpoint

        except Exception as exc:
            logger.error("No se pudo inicializar ONVIF en %s: %s", self._ip, exc)
            self._cam_obj = None
            self._pullpoint = None

    def _parse_messages(self, notifications) -> tuple[int, int]:
        """
        Parsea NotificationMessage de ONVIF y cuenta entradas/salidas.
        Estructura confirmada en XNO-6120R:
          Data.State=1   → cruce activo  (contar)
          Data.State=0   → fin del cruce (ignorar)
          Data.Action=Left  → ENTRADA
          Data.Action=Right → SALIDA
        """
        NS = "http://www.onvif.org/ver10/schema"
        in_count = out_count = 0

        for msg in notifications:
            try:
                prop_op = getattr(msg.Message, "PropertyOperation", None)
                if hasattr(msg.Message, "get"):
                    prop_op = prop_op or msg.Message.get("PropertyOperation")
                if prop_op == "Initialized":
                    continue

                msg_el = msg.Message._value_1
                if msg_el is None:
                    continue

                dat_el = msg_el.find(f"{{{NS}}}Data")
                if dat_el is None:
                    continue

                state = None
                action = ""
                for item in dat_el:
                    name = item.get("Name", "").lower()
                    val = item.get("Value", "").lower()
                    if name == "state":
                        state = val
                    elif name == "action":
                        action = val

                if state not in ("1", "true"):
                    continue

                if "left" in action:
                    in_count += 1
                elif "right" in action:
                    out_count += 1
                else:
                    in_count += 1  # Sin campo Action → asumir entrada

            except Exception as e:
                logger.debug("Error parseando mensaje ONVIF: %s", e)

        return in_count, out_count
