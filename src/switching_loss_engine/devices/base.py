from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..calibration import CalibrationProfile


class DeviceDefinition(ABC):
    device_id: str
    vendor: str

    def __init__(self, library_dir: Path):
        self.library_dir = library_dir

    @property
    @abstractmethod
    def data(self):
        raise NotImplementedError

    @abstractmethod
    def default_calibration_id(self, model: str) -> str | None:
        raise NotImplementedError

    def load_calibration(self, model: str, profile_id: str | None = None) -> CalibrationProfile | None:
        selected = profile_id or self.default_calibration_id(model)
        if selected is None:
            return None
        profile = CalibrationProfile.load(self.library_dir / "calibration" / f"{selected}.yaml")
        profile.validate_for(self.device_id, model)
        return profile

