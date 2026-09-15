from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .exceptions import InputValidationError


class ModelName(str, Enum):
    M0 = "M0"
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"


@dataclass(frozen=True)
class OperatingPointInput:
    vdc_V: float
    id_A: float
    tj_C: float = 25.0
    rg_on_ohm: float = 2.5
    rg_off_ohm: float = 2.5
    vg_on_V: float = 20.0
    vg_off_V: float = -5.0
    fsw_Hz: float = 100e3

    def validate(self) -> None:
        values = asdict(self)
        for key, value in values.items():
            if not isinstance(value, (int, float)):
                raise InputValidationError(f"{key} must be numeric")
        if not 0 < self.vdc_V <= 1200:
            raise InputValidationError("vdc_V must be in (0, 1200]")
        if not 0 < self.id_A <= 120:
            raise InputValidationError("id_A must be in (0, 120]")
        if not -55 <= self.tj_C <= 150:
            raise InputValidationError("tj_C must be in [-55, 150]")
        if self.rg_on_ohm < 0 or self.rg_off_ohm < 0:
            raise InputValidationError("gate resistances must be non-negative")
        if self.vg_on_V <= self.vg_off_V:
            raise InputValidationError("vg_on_V must exceed vg_off_V")
        if self.fsw_Hz < 0:
            raise InputValidationError("fsw_Hz must be non-negative")


@dataclass(frozen=True)
class ParasiticsInput:
    r_driver_on_ohm: float = 0.5
    r_driver_off_ohm: float = 0.5
    lg_H: float = 5e-9
    ls_H: float = 5e-9
    lloop_H: float = 20e-9
    rloop_ohm: float = 0.05
    loop_loss_fraction: float = 0.25

    def validate(self) -> None:
        for key, value in asdict(self).items():
            if value < 0:
                raise InputValidationError(f"{key} must be non-negative")
        if self.loop_loss_fraction > 1:
            raise InputValidationError("loop_loss_fraction must be <= 1")


@dataclass(frozen=True)
class CalculationRequest:
    device_id: str
    model: ModelName | str
    operating_point: OperatingPointInput
    parasitics: ParasiticsInput = field(default_factory=ParasiticsInput)
    calibration_id: str | None = None
    return_waveforms: bool = False
    time_step_s: float = 0.1e-9
    convergence_check: bool = True

    def validate(self) -> None:
        self.operating_point.validate()
        self.parasitics.validate()
        try:
            ModelName(self.model)
        except ValueError as exc:
            raise InputValidationError(f"unsupported model: {self.model}") from exc
        if not 0.01e-9 <= self.time_step_s <= 2e-9:
            raise InputValidationError("time_step_s must be in [0.01 ns, 2 ns]")


@dataclass
class SolverStatus:
    converged: bool
    code: str
    message: str
    time_step_s: float | None = None
    refinement_time_step_s: float | None = None
    eon_relative_change: float | None = None
    eoff_relative_change: float | None = None
    stage_steps: dict[str, int] = field(default_factory=dict)


@dataclass
class EnergyResult:
    eon_J: float
    eoff_J: float
    esw_J: float
    psw_W: float


@dataclass
class CalculationResult:
    schema_version: str
    engine_version: str
    device_id: str
    vendor: str
    model: str
    calibration_id: str | None
    input: dict[str, Any]
    energy: EnergyResult
    timing_s: dict[str, float]
    stress: dict[str, float]
    components_J: dict[str, float]
    solver: SolverStatus
    uncertainty: dict[str, Any]
    provenance: dict[str, Any]
    warnings: list[str]
    waveforms: dict[str, Any] | None = None

    def as_dict(self, include_waveforms: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_waveforms:
            value.pop("waveforms", None)
        return value

