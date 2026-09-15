from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Provenance:
    source_file: str
    source_sha256: str
    extractor: str
    extractor_version: str
    page: int | None = None
    locator: str | None = None
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ExtractedParameter:
    name: str
    value: float | str
    unit: str | None
    provenance: Provenance
    conditions: dict[str, float | str] = field(default_factory=dict)
    confidence: float = 1.0
    raw_text: str | None = None

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name cannot be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")


@dataclass
class DeviceRecord:
    schema_version: str
    device_id: str
    vendor: str
    part_number: str
    technology: str | None = None
    package: str | None = None
    ratings: dict[str, float | str] = field(default_factory=dict)
    parameters: list[ExtractedParameter] = field(default_factory=list)
    curve_assets: list[dict[str, Any]] = field(default_factory=list)
    model_assets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.device_id or not self.vendor or not self.part_number:
            raise ValueError("device_id, vendor, and part_number are required")
        for parameter in self.parameters:
            parameter.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


@dataclass
class ExtractionReport:
    schema_version: str
    status: str
    source_file: str
    source_sha256: str
    extractor: str
    parameters: list[ExtractedParameter] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

