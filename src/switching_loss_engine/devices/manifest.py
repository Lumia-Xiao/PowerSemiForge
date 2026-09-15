from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import InputValidationError


def load_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {"schema_version", "device_id", "vendor", "part_number", "curves", "calibrations"}
    missing = required - set(raw or {})
    if missing:
        raise InputValidationError(f"manifest missing fields: {sorted(missing)}")
    return raw

