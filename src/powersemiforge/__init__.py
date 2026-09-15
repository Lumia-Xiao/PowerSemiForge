"""PowerSemiForge public API."""

from switching_loss_engine import (
    CalculationRequest,
    CalculationResult,
    ModelName,
    OperatingPointInput,
    ParasiticsInput,
    available_devices,
    calculate,
)

from .schema import DeviceRecord, ExtractedParameter, ExtractionReport, Provenance

__version__ = "0.1.0"

__all__ = [
    "CalculationRequest", "CalculationResult", "ModelName", "OperatingPointInput",
    "ParasiticsInput", "available_devices", "calculate", "DeviceRecord",
    "ExtractedParameter", "ExtractionReport", "Provenance",
]

