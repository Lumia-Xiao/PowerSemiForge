from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ValidationPoint:
    split: str
    id_A: float
    tj_C: float
    eon_J: float
    eoff_J: float


@dataclass(frozen=True)
class ValidationDataset:
    dataset_id: str
    device_id: str
    conditions: dict[str, float]
    points: tuple[ValidationPoint, ...]
    source: str

    @classmethod
    def load(cls, path: str | Path) -> "ValidationDataset":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(raw["dataset_id"], raw["device_id"],
                   {k: float(v) for k, v in raw["conditions"].items()},
                   tuple(ValidationPoint(**p) for p in raw["points"]), raw["source"])

