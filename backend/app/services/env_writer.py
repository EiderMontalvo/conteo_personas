"""Mantiene las entradas CAMERA_{n}_* del .env sincronizadas con la BD.

Escribe en .env.tmp y hace os.replace(), que es atómico, para no corromper el .env.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CAMERA_KEY_RE = re.compile(r"^(#\s*)?CAMERA_(\d+)_(\w+)\s*=", re.IGNORECASE)


class EnvWriter:
    def __init__(self, env_path: Path) -> None:
        self._env_path = env_path
        self._tmp_path = env_path.with_suffix(".env.tmp")

    def set_camera(
        self,
        index: int,
        *,
        ip: str,
        name: str,
        role: str = "both",
        group: Optional[str] = None,
    ) -> None:
        """Las claves que no existían se añaden al final del .env."""
        lines = self._read_lines()
        updates = {
            f"CAMERA_{index}_IP": ip,
            f"CAMERA_{index}_NAME": name,
            f"CAMERA_{index}_ROLE": role,
        }
        if group:
            updates[f"CAMERA_{index}_GROUP"] = group

        lines, touched_keys = self._apply_updates(lines, index, updates)

        for key, value in updates.items():
            if key not in touched_keys:
                lines.append(f"{key}={value}\n")

        self._write_atomic(lines)
        logger.info("EnvWriter: cámara %d actualizada en .env (ip=%s, name=%s).", index, ip, name)

    def remove_camera(self, index: int) -> None:
        """Comenta las líneas CAMERA_{index}_* (no las borra)."""
        lines = self._read_lines()
        result = []
        for line in lines:
            m = _CAMERA_KEY_RE.match(line)
            if m and int(m.group(2)) == index and not line.startswith("#"):
                result.append(f"# {line}")
            else:
                result.append(line)
        self._write_atomic(result)
        logger.info("EnvWriter: cámara %d comentada en .env.", index)

    def _read_lines(self) -> list[str]:
        if not self._env_path.exists():
            return []
        return self._env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    def _apply_updates(
        self,
        lines: list[str],
        index: int,
        updates: dict[str, str],
    ) -> tuple[list[str], set[str]]:
        """Reemplaza en su sitio las claves de `updates`; devuelve también las ya escritas."""
        touched: set[str] = set()
        result = []
        for line in lines:
            m = _CAMERA_KEY_RE.match(line)
            if m and int(m.group(2)) == index:
                key = f"CAMERA_{index}_{m.group(3).upper()}"
                if key in updates:
                    result.append(f"{key}={updates[key]}\n")
                    touched.add(key)
                    continue
            result.append(line)
        return result, touched

    def _write_atomic(self, lines: list[str]) -> None:
        self._tmp_path.write_text("".join(lines), encoding="utf-8")
        os.replace(self._tmp_path, self._env_path)
