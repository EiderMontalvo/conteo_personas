"""Cliente simulado con la interfaz de OnvifCameraClient, para DEMO_MODE=true.

Genera ráfagas de entradas, salidas que siguen a las entradas y periodos sin actividad.
"""
from __future__ import annotations

import asyncio
import random

from app.integrations.onvif.client import CountData


class SimulatedCameraClient:
    def __init__(self, ip: str, *, pull_timeout: int = 3, seed: int | None = None) -> None:
        self.ip = ip
        self._pull_timeout = pull_timeout
        self._rng = random.Random(seed)
        self._inside = 0
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        await asyncio.sleep(0.2)
        self._connected = True

    async def pull(self) -> CountData:
        # Imita el long-poll real: espera hasta pull_timeout
        await asyncio.sleep(self._rng.uniform(0.5, self._pull_timeout))
        if self._rng.random() < 0.35:
            return CountData(0, 0)

        new_in = self._rng.choice((0, 1, 1, 1, 2, 3))
        # Las salidas dependen de cuánta gente hay dentro
        max_out = min(self._inside, 3)
        new_out = self._rng.randint(0, max_out) if max_out else 0
        self._inside = max(0, self._inside + new_in - new_out)
        return CountData(new_in, new_out)

    async def close(self) -> None:
        self._connected = False
