from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
import yaml

from switching_loss_engine import CalculationRequest, OperatingPointInput, ParasiticsInput, calculate


GRID_FIELDS = ("vdc_V", "id_A", "tj_C", "rg_on_ohm", "rg_off_ohm", "vg_on_V", "vg_off_V", "fsw_Hz")


def load_matrix(path: str | Path) -> dict[str, Any]:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not config.get("devices") or not config.get("models") or not config.get("grid"):
        raise ValueError("matrix requires devices, models, and grid")
    return config


def expand_matrix(config: dict[str, Any]) -> list[dict[str, Any]]:
    grid = config["grid"]
    values = []
    for field in GRID_FIELDS:
        default = {"tj_C": [25.0], "rg_on_ohm": [2.5], "rg_off_ohm": [2.5],
                   "vg_on_V": [20.0], "vg_off_V": [-5.0], "fsw_Hz": [100e3]}.get(field)
        selected = grid.get(field, default)
        if selected is None:
            raise ValueError(f"matrix grid missing {field}")
        values.append(selected if isinstance(selected, list) else [selected])
    jobs = []
    for device, model, point in product(config["devices"], config["models"], product(*values)):
        jobs.append({"device_id": device, "model": model, **dict(zip(GRID_FIELDS, point))})
    return jobs


def run_batch(matrix_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    matrix_path = Path(matrix_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_matrix(matrix_path)
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    run_id = sha256(canonical.encode()).hexdigest()[:16]
    parasitics = ParasiticsInput(**config.get("parasitics", {}))
    options = config.get("options", {})
    rows, failures = [], []
    start = perf_counter()
    for index, job in enumerate(expand_matrix(config)):
        try:
            request = CalculationRequest(
                job["device_id"], job["model"],
                OperatingPointInput(**{field: job[field] for field in GRID_FIELDS}),
                parasitics=parasitics, calibration_id=options.get("calibration_id"),
                return_waveforms=False, time_step_s=float(options.get("time_step_s", 0.1e-9)),
                convergence_check=bool(options.get("convergence_check", False)),
            )
            result = calculate(request)
            rows.append({"run_id": run_id, "job_index": index, **job,
                         "eon_J": result.energy.eon_J, "eoff_J": result.energy.eoff_J,
                         "esw_J": result.energy.esw_J, "psw_W": result.energy.psw_W,
                         "solver_converged": result.solver.converged,
                         "calculation_seconds": result.provenance["calculation_seconds"],
                         "calibration_id": result.calibration_id})
        except Exception as exc:
            failures.append({"job_index": index, **job, "error": f"{type(exc).__name__}: {exc}"})
    pd.DataFrame(rows).to_csv(output_dir / "results.csv", index=False)
    (output_dir / "failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
    manifest = {"schema_version": "1.0", "run_id": run_id, "matrix": str(matrix_path.resolve()),
                "jobs": len(rows) + len(failures), "completed": len(rows), "failed": len(failures),
                "elapsed_seconds": perf_counter() - start, "config": config}
    (output_dir / "run-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

