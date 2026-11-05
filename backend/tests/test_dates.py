"""Los límites de día siguen la zona horaria del negocio (America/Lima, UTC-5)."""
from datetime import datetime, timezone

from app.core.dates import local_today_start_utc, parse_date


def test_today_after_7pm_lima_is_still_today():
    # 21:00 en Lima del día 4 = 02:00 UTC del día 5
    now = datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)
    assert local_today_start_utc(now) == datetime(2026, 11, 4, 5, 0, tzinfo=timezone.utc)


def test_parse_date_is_local_midnight():
    assert parse_date("2026-11-06") == datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc)


def test_parse_date_invalid_is_ignored():
    assert parse_date("06/11/2026") is None
    assert parse_date("") is None


def test_local_date_of_naive_utc_timestamp():
    from app.core.dates import local_date
    # 02:37 UTC del día 5 (naive, como lo devuelve SQLite) = día 4 en Lima
    assert local_date(datetime(2026, 11, 5, 2, 37)).isoformat() == "2026-11-04"
