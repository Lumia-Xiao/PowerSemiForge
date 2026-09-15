from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from .schemas import CalculationResult


def export_json(result: CalculationResult, path: str | Path, include_waveforms: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_dict(include_waveforms), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_summary_csv(result: CalculationResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "device_id": result.device_id, "model": result.model, "calibration_id": result.calibration_id,
        "eon_J": result.energy.eon_J, "eoff_J": result.energy.eoff_J,
        "esw_J": result.energy.esw_J, "psw_W": result.energy.psw_W,
        "solver_converged": result.solver.converged,
        **{f"op_{k}": v for k, v in result.input["operating_point"].items()},
        **{f"par_{k}": v for k, v in result.input["parasitics"].items()},
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return path


def export_waveform_csvs(result: CalculationResult, directory: str | Path) -> dict[str, Path]:
    if not result.waveforms:
        raise ValueError("result has no waveforms; set return_waveforms=True")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for event, records in result.waveforms.items():
        path = directory / f"{result.device_id}_{result.model}_{event}.csv"
        pd.DataFrame(records).to_csv(path, index=False)
        paths[event] = path
    return paths

