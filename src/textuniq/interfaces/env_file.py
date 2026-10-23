"""Минимальная загрузка .env: KEY=VALUE построчно, уже заданные переменные не трогаем."""

import os
from pathlib import Path


def load_env_file(path: Path) -> bool:
    path = Path(path)
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
    return True
