"""Parseo de fechas 'YYYY-MM-DD' en hora local del negocio y rangos inclusivos."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz

from app.core.config import settings


def _tz():
    return pytz.timezone(settings.timezone)


def local_today_start_utc(now: Optional[datetime] = None) -> datetime:
    """Medianoche de hoy en la zona horaria del negocio, expresada en UTC."""
    now_local = (now or datetime.now(timezone.utc)).astimezone(_tz())
    midnight = _tz().localize(datetime(now_local.year, now_local.month, now_local.day))
    return midnight.astimezone(timezone.utc)


def local_date(ts: datetime):
    """Día local del negocio de un timestamp UTC (SQLite lo devuelve naive)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(_tz()).date()


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    'YYYY-MM-DD' (día local) -> medianoche local en UTC, para que "2026-11-06"
    abarque ese día en Lima y no de 19:00 a 19:00.

    Devuelve None si está vacío o es inválido: el filtro se ignora sin romper el endpoint.
    """
    if not date_str:
        return None
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    return _tz().localize(day).astimezone(timezone.utc)


def end_of_day_inclusive(dt_to: Optional[datetime]) -> Optional[datetime]:
    """Suma 1 día al límite superior para hacerlo inclusivo (el repo filtra con `timestamp < dt_to`)."""
    if dt_to is None:
        return None
    return dt_to + timedelta(days=1)