from __future__ import annotations

from pathlib import Path

from ..exceptions import DeviceNotFoundError
from .base import DeviceDefinition


class DeviceRegistry:
    def __init__(self, library_root: Path):
        self.library_root = library_root
        self._factories = {}

    def register(self, device_id: str, factory) -> None:
        self._factories[device_id.upper()] = factory

    def create(self, device_id: str) -> DeviceDefinition:
        key = device_id.upper()
        if key not in self._factories:
            raise DeviceNotFoundError(f"unknown device: {device_id}; available={self.available()}")
        return self._factories[key](self.library_root)

    def available(self) -> list[str]:
        return sorted(self._factories)
