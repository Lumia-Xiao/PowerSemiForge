from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ..exceptions import CalibrationError


@dataclass(frozen=True)
class CorrectionTable:
    x: tuple[float, ...]
    eon: tuple[float, ...]
    eoff: tuple[float, ...]

    def factor(self, xq: float, which: str) -> float:
        values = self.eon if which == "Eon" else self.eoff
        return float(np.interp(xq, self.x, values, left=values[0], right=values[-1]))


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    version: int
    device_id: str
    model: str
    scale_on: float
    scale_off: float
    reference: dict[str, float]
    reference_parasitics: dict[str, float]
    source: dict[str, Any]
    current_correction: CorrectionTable | None = None
    temperature_correction: CorrectionTable | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def factor(self, current_A: float, temperature_C: float, which: str) -> float:
        factor = self.scale_on if which == "Eon" else self.scale_off
        if self.current_correction:
            factor *= self.current_correction.factor(current_A, which)
        if self.temperature_correction:
            factor *= self.temperature_correction.factor(temperature_C, which)
        return float(factor)

    @staticmethod
    def _table(data: dict[str, Any] | None) -> CorrectionTable | None:
        if not data:
            return None
        table = CorrectionTable(tuple(map(float, data["x"])), tuple(map(float, data["eon"])), tuple(map(float, data["eoff"])))
        if not (len(table.x) == len(table.eon) == len(table.eoff)) or len(table.x) < 2:
            raise CalibrationError("correction table lengths are invalid")
        return table

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationProfile":
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return cls(
                profile_id=str(raw["profile_id"]), version=int(raw["version"]),
                device_id=str(raw["device_id"]), model=str(raw["model"]),
                scale_on=float(raw["scale_on"]), scale_off=float(raw["scale_off"]),
                reference={k: float(v) for k, v in raw["reference"].items()},
                reference_parasitics={k: float(v) for k, v in raw["reference_parasitics"].items()},
                source=dict(raw.get("source", {})),
                current_correction=cls._table(raw.get("current_correction")),
                temperature_correction=cls._table(raw.get("temperature_correction")),
                metadata=dict(raw.get("metadata", {})),
            )
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            raise CalibrationError(f"cannot load calibration profile {path}: {exc}") from exc

    def validate_for(self, device_id: str, model: str) -> None:
        if self.device_id != device_id or self.model != model:
            raise CalibrationError(
                f"profile {self.profile_id} targets {self.device_id}/{self.model}, not {device_id}/{model}"
            )
        if self.scale_on <= 0 or self.scale_off <= 0:
            raise CalibrationError("calibration scales must be positive")

