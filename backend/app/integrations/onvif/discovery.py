"""
app/integrations/onvif/discovery.py
-------------------------------------
Descubrimiento de cámaras ONVIF en la red local.

Estrategia en cascada:
  1. WS-Discovery (ONVIF estándar, UDP multicast puerto 3702).
     Funciona si ONVIF está habilitado en la cámara Hanwha.
  2. TCP scan del rango de la subred local (puerto 80).
     Fallback si el firewall bloquea multicast o la cámara no responde WS-D.
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

# Timeout por intento TCP (segundos) — valor bajo para no tardar demasiado
_TCP_TIMEOUT = 0.35
# Máximo de IPs a escanear en paralelo con TCP
_TCP_CONCURRENCY = 50
# Timeout para WS-Discovery
_WSD_TIMEOUT = 5


async def discover_cameras(timeout: float = _WSD_TIMEOUT) -> List[DiscoveredCamera]:
    """
    Descubre cámaras ONVIF en la red local.
    Primero intenta WS-Discovery; si no encuentra nada, hace TCP scan.
    """
    logger.info("Iniciando descubrimiento de cámaras en la red local...")

    # Método 1: WS-Discovery
    found = await _discover_ws(timeout)
    if found:
        logger.info("WS-Discovery encontró %d dispositivo(s).", len(found))
        return found

    # Método 2: TCP scan de la subred
    logger.info("WS-Discovery sin resultados. Iniciando TCP scan...")
    found = await _discover_tcp()
    logger.info("TCP scan encontró %d dispositivo(s).", len(found))
    return found


# ── WS-Discovery ──────────────────────────────────────────────────────────────

async def _discover_ws(timeout: float) -> List[DiscoveredCamera]:
    """Usa el protocolo WS-Discovery (ONVIF) para encontrar cámaras."""
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
    """Versión síncrona de WS-Discovery (ejecutada en thread pool)."""
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
                        manufacturer="Hanwha",  # Asumimos Hanwha en este proyecto
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
        # Parsear la URL manualmente para evitar imports extra
        parts = xaddr.replace("http://", "").replace("https://", "").split("/")[0]
        host = parts.split(":")[0]
        ipaddress.ip_address(host)  # Validar que es IP válida
        return host
    except Exception:
        return None


def _guess_model(svc) -> str:
    """Intenta obtener el modelo del servicio WS-Discovery."""
    try:
        types = str(svc.getTypes())
        if "NetworkVideoTransmitter" in types:
            return "Wisenet"
    except Exception:
        pass
    return "Desconocido"


# ── TCP Scan ──────────────────────────────────────────────────────────────────

async def _discover_tcp() -> List[DiscoveredCamera]:
    """
    Escanea el rango /24 de la IP local buscando puerto 80 abierto.
    Solo incluye hosts que respondan como dispositivos Hanwha.
    """
    local_ip = _get_local_ip()
    if not local_ip:
        logger.warning("No se pudo determinar la IP local para el TCP scan.")
        return []

    # Construir rango /24 (ej. 192.168.1.0/24)
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
    """
    Comprueba si un host tiene el puerto 80 abierto y responde como cámara Hanwha.
    """
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

        # Puerto abierto — intentar identificar como cámara Hanwha
        manufacturer, model = await _identify_camera(ip)
        if manufacturer:
            return DiscoveredCamera(ip=ip, port=port, manufacturer=manufacturer, model=model)

    return None


async def _identify_camera(ip: str) -> tuple[str, str]:
    """
    Intenta identificar el fabricante/modelo de un dispositivo via HTTP.
    Prueba el endpoint de información de dispositivo de Hanwha Wisenet.
    """
    urls = [
        f"http://{ip}/stw-cgi/system.cgi?msubmenu=deviceinfo&action=view",
        f"http://{ip}/onvif/device_service",  # ONVIF device
    ]
    async with httpx.AsyncClient(timeout=1.5) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                text = resp.text.lower()
                if any(kw in text for kw in ("hanwha", "wisenet", "samsung techwin", "xno", "qno")):
                    # Extraer modelo si es posible
                    model = _parse_model_from_response(resp.text)
                    return "Hanwha", model
                if resp.status_code == 200:
                    # Responde HTTP pero no es Hanwha confirmada
                    return "Desconocido", "Desconocido"
            except Exception:
                continue
    return "", ""


def _parse_model_from_response(text: str) -> str:
    """Parsea el modelo del dispositivo desde la respuesta HTTP."""
    import re
    # Buscar patrones como "Model=XNO-6120R" o "<Model>XNO-6120R</Model>"
    for pattern in [
        r'Model[=:>]\s*([A-Z0-9\-]+)',
        r'"model"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Wisenet"


def _get_local_ip() -> Optional[str]:
    """Obtiene la IP local de la máquina (la que usa para salir a la LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None
