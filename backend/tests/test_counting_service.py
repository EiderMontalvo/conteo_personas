"""CountingService: roles, estado del día persistido y reinicio diario."""
from datetime import datetime, timezone

import pytest

from app.models.counting import CountingEvent
from app.repositories.camera_repo import camera_repo
from app.services.counting_service import CountingService

# 15:00 en Lima (UTC-5)
T0 = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)


async def _process(svc, db, raw_in, raw_out, *, role="both", now=T0, cap=None):
    await svc.process(
        camera_id=0, camera_name="Cam", camera_role=role, camera_group=None,
        raw_in=raw_in, raw_out=raw_out, db=db, max_capacity=cap, now_utc=now,
    )


@pytest.mark.asyncio
async def test_activity_updates_persisted_state(db):
    svc = CountingService()
    await _process(svc, db, 3, 0)
    await _process(svc, db, 1, 2)

    state = camera_repo.get_state(db, 0)
    assert (state.total_in, state.total_out, state.people_inside) == (4, 2, 2)
    events = db.query(CountingEvent).filter_by(event_type="change_event").all()
    assert [e.people_inside for e in events] == [3, 2]


@pytest.mark.asyncio
async def test_people_inside_never_negative(db):
    svc = CountingService()
    await _process(svc, db, 0, 5)
    assert camera_repo.get_state(db, 0).people_inside == 0


@pytest.mark.asyncio
async def test_state_survives_restart(db):
    first = CountingService()
    await _process(first, db, 5, 1)

    restarted = CountingService()  # nuevo proceso: RAM vacía
    await _process(restarted, db, 1, 0, now=T0.replace(minute=30))
    state = camera_repo.get_state(db, 0)
    assert (state.total_in, state.people_inside) == (6, 5)


@pytest.mark.asyncio
async def test_totals_reset_on_new_local_day(db):
    svc = CountingService()
    await _process(svc, db, 5, 0)
    # 06:00 UTC del día 7 = 01:00 en Lima del día 7 → día nuevo
    await _process(svc, db, 1, 0, now=datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc))
    state = camera_repo.get_state(db, 0)
    assert (state.total_in, state.people_inside) == (1, 1)


@pytest.mark.asyncio
async def test_same_local_day_across_utc_midnight_is_not_reset(db):
    svc = CountingService()
    await _process(svc, db, 2, 0)
    # 03:00 UTC del día 7 = 22:00 en Lima del día 6 → mismo día
    await _process(svc, db, 1, 0, now=datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc))
    assert camera_repo.get_state(db, 0).total_in == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [("in_only", (2, 0)), ("out_only", (0, 1)), ("space", (2, 1))])
async def test_roles_filter_directions(db, role, expected):
    svc = CountingService()
    await _process(svc, db, 2, 1, role=role)
    state = camera_repo.get_state(db, 0)
    assert (state.total_in, state.total_out) == expected


@pytest.mark.asyncio
async def test_capacity_status(db):
    svc = CountingService()
    await _process(svc, db, 9, 0, cap=10)
    assert camera_repo.get_state(db, 0).status in ("Advertencia", "Crítico")
    await _process(svc, db, 5, 0, cap=10)
    assert camera_repo.get_state(db, 0).status == "Excedido"


@pytest.mark.asyncio
async def test_hourly_heartbeat_without_activity(db):
    svc = CountingService()
    await _process(svc, db, 0, 0)
    await _process(svc, db, 0, 0, now=T0.replace(minute=30))
    await _process(svc, db, 0, 0, now=T0.replace(hour=21, minute=1))
    beats = db.query(CountingEvent).filter_by(event_type="hourly_heartbeat").count()
    assert beats == 2
