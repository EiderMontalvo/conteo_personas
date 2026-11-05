"""Descubrimiento de cámaras ONVIF en la LAN.

Primero WS-Discovery (multicast UDP 3702); si no hay respuesta (p. ej. firewall), escaneo TCP del /24 local.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import List, Optional

import httpx

from app.schemas.camera import DiscoveredCamera

logger = logging.getLogger(__name__)

# Bajo para que el escaneo del /24 no tarde demasiado (segundos)
_TCP_TIMEOUT = 0.35
_TCP_CONCURRENCY = 50
_WSD_TIMEOUT = 5


async def discover_cameras(timeout: float = _WSD_TIMEOUT) -> List[DiscoveredCamera]:
    logger.info("Iniciando descubrimiento de cámaras en la red local...")

    found = await _discover_ws(timeout)
    if found:
        logger.info("WS-Discovery encontró %d dispositivo(s).", len(found))
        return found

    logger.info("WS-Discovery sin resultados. Iniciando TCP scan...")
    found = await _discover_tcp()
    logger.info("TCP scan encontró %d dispositivo(s).", len(found))
    return found


async def _discover_ws(timeout: float) -> List[DiscoveredCamera]:
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _ws_discovery_sync, timeout),
            timeout=timeout + 2,
        )
    except asyncio.TimeoutError:
        logger.warning("WS-Discovery timeout.")
        return []
    except Exception as exc:
        logger.warning("WS-Discovery falló: %s", exc)
        return []


def _ws_discovery_sync(timeout: float) -> List[DiscoveredCamera]:
    results: List[DiscoveredCamera] = []
    try:
        from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
        from wsdiscovery import Scope

        wsd = WSDiscovery()
        wsd.start()
        try:
            scope = Scope("onvif://www.onvif.org/Profile")
            services = wsd.searchServices(scopes=[scope], timeout=int(timeout))
            for svc in services:
                addrs = svc.getXAddrs()
                if not addrs:
                    continue
                ip = _extract_ip_from_xaddr(addrs[0])
                if ip:
                    results.append(DiscoveredCamera(
                        ip=ip,
                        port=80,
                        manufacturer="Hanwha",  # el proyecto solo usa cámaras Hanwha
                        model=_guess_model(svc),
                    ))
        finally:
            wsd.stop()
    except ImportError:
        logger.warning("WSDiscovery no instalado. Instala con: pip install WSDiscovery")
    except Exception as exc:
        logger.warning("Error en _ws_discovery_sync: %s", exc)
    return results


def _extract_ip_from_xaddr(xaddr: str) -> Optional[str]:
    """Extrae la IP de una XAddr ONVIF (ej. 'http://192.168.1.100:80/onvif/device_service')."""
    try:
        parts = xaddr.replace("http://", "").replace("https://", "").split("/")[0]
        host = parts.split(":")[0]
        ipaddress.ip_address(host)
        return host
    except Exception:
        return None


def _guess_model(svc) -> str:
    try:
        types = str(svc.getTypes())
        if "NetworkVideoTransmitter" in types:
            return "Wisenet"
    except Exception:
        pass
    return "Desconocido"


async def _discover_tcp() -> List[DiscoveredCamera]:
    local_ip = _get_local_ip()
    if not local_ip:
        logger.warning("No se pudo determinar la IP local para el TCP scan.")
        return []

    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    hosts = [str(h) for h in network.hosts()]
    logger.info("TCP scan en %s (%d hosts)...", network, len(hosts))

    sem = asyncio.Semaphore(_TCP_CONCURRENCY)
    tasks = [_check_host(ip, 80, sem) for ip in hosts]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: List[DiscoveredCamera] = []
    for r in results_raw:
        if isinstance(r, DiscoveredCamera):
            results.append(r)

    return results


async def _check_host(ip: str, port: int, sem: asyncio.Semaphore) -> Optional[DiscoveredCamera]:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=_TCP_TIMEOUT
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None

        manufacturer, model = await _identify_camera(ip)
        if manufacturer:
            return DiscoveredCamera(ip=ip, port=port, manufacturer=manufacturer, model=model)

    return None


async def _identify_camera(ip: str) -> tuple[str, str]:
    """Devuelve ("", "") si el host no responde HTTP; "Desconocido" si responde pero no es Hanwha."""
    urls = [
        f"http://{ip}/stw-cgi/system.cgi?msubmenu=deviceinfo&action=view",
        f"http://{ip}/onvif/device_service",
    ]
    async with httpx.AsyncClient(timeout=1.5) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                text = resp.text.lower()
                if any(kw in text for kw in ("hanwha", "wisenet", "samsung techwin", "xno", "qno")):
                    model = _parse_model_from_response(resp.text)
                    return "Hanwha", model
                if resp.status_code == 200:
                    return "Desconocido", "Desconocido"
            except Exception:
                continue
    return "", ""


def _parse_model_from_response(text: str) -> str:
    import re
    # p. ej. "Model=XNO-6120R" o "<Model>XNO-6120R</Model>"
    for pattern in [
        r'Model[=:>]\s*([A-Z0-9\-]+)',
        r'"model"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Wisenet"


def _get_local_ip() -> Optional[str]:
    """IP de la interfaz que sale a la LAN (el UDP connect no envía paquetes)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None
