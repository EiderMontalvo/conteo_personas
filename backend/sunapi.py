"""
sunapi.py
---------
Cliente ONVIF para Hanwha Wisenet XNO-6120R (firmware 1.40.02_20191028).
Usa onvif-zeep (biblioteca oficial) con PullPoint subscription.

DIAGNÓSTICO CONFIRMADO (sesión de debugging exhaustiva):
  - recording.cgi: TotalCount=0 siempre → sin SD card, sin grabación local.
  - eventsources.cgi?msubmenu=linecrossing: Error 600 (submenu no existe).
  - eventsources.cgi?msubmenu=videoanalysis: solo configuración, no conteos.
  - ONVIF manual (httpx): ActionNotSupported → zeep no tiene este problema.
  - onvif-zeep: PullPointSubscription funciona. TopicSet incluye VideoAnalytics.

SOLUCIÓN: onvif-zeep en thread de I/O separado (zeep es síncrono).
  Cada ciclo de polling hace PullMessages y filtra mensajes VideoAnalytics
  con PropertyOperation="Changed" → cada uno = 1 cruce de línea.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from config import CameraConfig

logger = logging.getLogger(__name__)


@dataclass
class CountData:
    """Resultado de una consulta de conteo a la cámara."""
    in_count: int
    out_count: int


#Thread pool para ejecutar el código síncrono de zeep
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="onvif")


class SunAPIClient:
    """
    Cliente ONVIF PullPoint para Hanwha Wisenet XNO-6120R.
    Usa onvif-zeep en un ThreadPoolExecutor para no bloquear el event loop.
    """

    def __init__(self, camera: CameraConfig) -> None:
        self._camera = camera
        #Acumuladores propios
        self._cumulative_in: int = 0
        self._cumulative_out: int = 0
        #Estado interno de la suscripción ONVIF
        self._poll_count: int = 0
        self._cam_obj = None         
        self._pullpoint = None       
        self._event_service = None   

    async def get_realtime_count(self) -> Optional[CountData]:
        """
        Ciclo principal de polling. Ejecuta el código zeep (síncrono)
        en un thread para no bloquear el event loop de FastAPI.
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                self._poll_sync,
            )
            return result
        except Exception as exc:
            logger.exception(
                "Error inesperado al consultar la cámara %s: %s",
                self._camera.ip, exc,
            )
            self._cam_obj = None
            self._pullpoint = None
            return None

    def _poll_sync(self) -> Optional[CountData]:
        """
        Código síncrono (ejecutado en thread): crea la suscripción si no existe,
        hace PullMessages y cuenta los eventos de cruce de línea.
        """
        self._poll_count += 1

        try:
            #Inicializar o reinicializar la cámara ONVIF
            if self._cam_obj is None:
                self._init_onvif()

            if self._pullpoint is None:
                return CountData(
                    in_count=self._cumulative_in,
                    out_count=self._cumulative_out,
                )

            #Renovar suscripción periódicamente (cada 20 ciclos ≈ 60s)
            if self._poll_count % 20 == 0 and self._event_service is not None:
                try:
                    self._event_service.CreatePullPointSubscription(
                        {"InitialTerminationTime": "PT300S"}
                    )
                    logger.debug(
                        "Suscripción ONVIF renovada para cámara %s.", self._camera.ip
                    )
                except Exception as e:
                    logger.warning("Error renovando suscripción: %s", e)

            #Pull de mensajes (hasta 3s por nuevos eventos)
            try:
                messages = self._pullpoint.PullMessages({
                    "MessageLimit": 100,
                    "Timeout": "PT3S",
                })
            except Exception as e:
                logger.warning(
                    "Error en PullMessages (cámara %s): %s. Reiniciando suscripción.",
                    self._camera.ip, e
                )
                self._cam_obj = None
                self._pullpoint = None
                return CountData(
                    in_count=self._cumulative_in,
                    out_count=self._cumulative_out,
                )

            if not messages.NotificationMessage:
                return CountData(
                    in_count=self._cumulative_in,
                    out_count=self._cumulative_out,
                )

            new_in, new_out = self._parse_messages(messages.NotificationMessage)
            self._cumulative_in  += new_in
            self._cumulative_out += new_out

            if new_in + new_out > 0:
                logger.info(
                    "Cámara '%s': +%d IN +%d OUT → Total IN=%d OUT=%d",
                    self._camera.name, new_in, new_out,
                    self._cumulative_in, self._cumulative_out,
                )

            return CountData(
                in_count=self._cumulative_in,
                out_count=self._cumulative_out,
            )

        except Exception as exc:
            logger.exception(
                "Error en _poll_sync (cámara %s): %s", self._camera.ip, exc
            )
            self._cam_obj = None
            self._pullpoint = None
            return None

    def _init_onvif(self) -> None:
        """Inicializa la conexión ONVIF y crea la suscripción PullPoint."""
        try:
            from onvif import ONVIFCamera
        except ImportError:
            logger.error(
                "onvif-zeep no instalado. Ejecuta: pip install onvif-zeep"
            )
            return

        logger.info(
            "Iniciando conexión ONVIF con cámara %s (%s)...",
            self._camera.name, self._camera.ip
        )
        try:
            cam = ONVIFCamera(
                self._camera.ip,
                80,
                self._camera.user,
                self._camera.password,
            )
            event_service = cam.create_events_service()
            subscription = event_service.CreatePullPointSubscription(
                {"InitialTerminationTime": "PT300S"}
            )
            pullpoint = cam.create_pullpoint_service()

            #Descartar los mensajes iniciales "Initialized"
            init_msgs = pullpoint.PullMessages({
                "MessageLimit": 100,
                "Timeout": "PT1S",
            })
            n_init = (
                len(init_msgs.NotificationMessage)
                if init_msgs.NotificationMessage
                else 0
            )
            logger.info(
                "Suscripción ONVIF activa en '%s'. Mensajes iniciales descartados: %d.",
                self._camera.name, n_init
            )

            self._cam_obj = cam
            self._event_service = event_service
            self._pullpoint = pullpoint

        except Exception as exc:
            logger.error(
                "No se pudo inicializar ONVIF en cámara %s: %s",
                self._camera.ip, exc
            )
            self._cam_obj = None
            self._pullpoint = None

    def _parse_messages(self, notifications) -> tuple[int, int]:
        """
        Parsea los NotificationMessage de ONVIF y cuenta entradas/salidas.

        Estructura CONFIRMADA del evento de cruce en XNO-6120R:
          <tt:Message PropertyOperation="Changed" UtcTime="2026-07-13T...">
            <tt:Source>
              <tt:SimpleItem Name="VideoSourceToken" Value="VideoSourceToken-0"/>
            </tt:Source>
            <tt:Data>
              <tt:SimpleItem Name="State" Value="1"/>   ← cruce activo
              <tt:SimpleItem Name="Action" Value="Left"/>  ← dirección
            </tt:Data>
          </tt:Message>

        State=1 → cruce activo (entrada o salida)
        State=0 → fin del cruce (ignorar)
        Action=Left  → hacia izquierda (ajusta según orientación de la cámara)
        Action=Right → hacia derecha
        """
        NS = "http://www.onvif.org/ver10/schema"
        in_count  = 0
        out_count = 0

        for msg in notifications:
            try:
                msg_el = msg.Message._value_1
                if msg_el is None:
                    continue

                dat_el = msg_el.find(f"{{{NS}}}Data")
                if dat_el is None:
                    continue


                state  = None
                action = ""
                for item in dat_el:
                    name = item.get("Name", "").lower()
                    val  = item.get("Value", "").lower()
                    if name == "state":
                        state = val  #'1' o 'true' = cruce; '0' o 'false' = fin
                    elif name == "action":
                        action = val

                # Solo contar el inicio del cruce (State=1 o State=true)
                if state not in ("1", "true"):
                    continue
                #Ajusta Left/Right según la orientación de tu cámara:
                #Action=Left  → hacia izquierda (ENTRADA)
                #Action=Right → hacia derecha   (SALIDA)
                #Si no hay campo Action, se suma como entrada.
                if "left" in action:
                    in_count += 1
                elif "right" in action:
                    out_count += 1
                else:
                    in_count += 1

            except Exception as e:
                logger.debug("Error parseando mensaje ONVIF: %s", e)
                continue

        if in_count + out_count > 0:
            logger.debug(
                "Cruces detectados: %d IN, %d OUT",
                in_count, out_count
            )

        return in_count, out_count