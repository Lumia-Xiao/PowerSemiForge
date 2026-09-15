from __future__ import annotations

from functools import cached_property
from pathlib import Path

from ...models.device_data import C2M0025120DData
from ..base import DeviceDefinition
from ..manifest import load_manifest


class C2M0025120D(DeviceDefinition):
    device_id = "C2M0025120D"
    vendor = "Wolfspeed"

    def __init__(self, library_root: Path):
        super().__init__(library_root / "wolfspeed" / self.device_id)
        self.manifest = load_manifest(self.library_dir / "manifest.yaml")

    @cached_property
    def data(self) -> C2M0025120DData:
        return C2M0025120DData(self.library_dir / "curves")

    def default_calibration_id(self, model: str) -> str | None:
        return self.manifest["calibrations"].get(model)
