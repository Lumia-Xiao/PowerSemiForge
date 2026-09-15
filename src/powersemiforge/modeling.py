from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Protocol


class ModelPlugin(Protocol):
    model_id: str
    device_id: str

    def predict(self, operating_point: dict[str, float], parasitics: dict[str, float]) -> dict[str, Any]: ...


@dataclass
class ModelRegistry:
    _models: dict[tuple[str, str], ModelPlugin]

    def __init__(self):
        self._models = {}

    def register(self, model: ModelPlugin) -> None:
        key = (model.device_id.upper(), model.model_id.upper())
        if key in self._models:
            raise ValueError(f"model already registered: {key}")
        self._models[key] = model

    def get(self, device_id: str, model_id: str) -> ModelPlugin:
        key = (device_id.upper(), model_id.upper())
        if key not in self._models:
            raise KeyError(f"model not registered: {key}")
        return self._models[key]


def _identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not cleaned:
        raise ValueError("cannot create Python identifier")
    if cleaned[0].isdigit():
        cleaned = f"Device_{cleaned}"
    return cleaned


def scaffold_model(device_dir: str | Path, model_id: str = "M0") -> dict[str, Path]:
    device_dir = Path(device_dir)
    manifest = device_dir / "manifest.yaml"
    if not manifest.exists():
        raise FileNotFoundError(f"device manifest not found: {manifest}")
    import yaml
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    device_id = str(data["device_id"])
    class_name = f"{_identifier(device_id)}{_identifier(model_id)}Model"
    model_dir = device_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    code_path = model_dir / f"{model_id.lower()}_model.py"
    test_path = model_dir / f"test_{model_id.lower()}_model.py"
    if code_path.exists() or test_path.exists():
        raise FileExistsError(f"model scaffold already exists for {device_id}/{model_id}")
    code = f'''from __future__ import annotations


class {class_name}:
    """{device_id} {model_id} model scaffold.

    Replace this scaffold with traceable equations. Do not fit calibration in predict().
    """

    device_id = "{device_id}"
    model_id = "{model_id}"

    def __init__(self, device_record, calibration_profile=None):
        self.device_record = device_record
        self.calibration_profile = calibration_profile

    def predict(self, operating_point: dict[str, float], parasitics: dict[str, float]):
        raise NotImplementedError("implement and validate {device_id}/{model_id}")
'''
    test = f'''import unittest

from {model_id.lower()}_model import {class_name}


class {class_name}Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual({class_name}.device_id, "{device_id}")
        self.assertEqual({class_name}.model_id, "{model_id}")


if __name__ == "__main__":
    unittest.main()
'''
    code_path.write_text(code, encoding="utf-8")
    test_path.write_text(test, encoding="utf-8")
    return {"model": code_path, "test": test_path}

