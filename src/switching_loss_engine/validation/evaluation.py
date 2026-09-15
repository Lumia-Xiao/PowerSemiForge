from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np

from ..api import calculate, device_library_root, project_root
from ..schemas import CalculationRequest, OperatingPointInput, ParasiticsInput
from .dataset import ValidationDataset


def _metrics(target: list[float], predicted: list[float]) -> dict[str, float]:
    y = np.asarray(target)
    p = np.asarray(predicted)
    absolute = np.abs(p - y)
    percentage = absolute / np.maximum(np.abs(y), 1e-15) * 100
    return {"mae_J": float(absolute.mean()), "rmse_J": float(np.sqrt(np.mean((p - y) ** 2))),
            "mape_pct": float(percentage.mean()), "p90_ape_pct": float(np.percentile(percentage, 90)),
            "max_ape_pct": float(percentage.max())}


def evaluate_dataset(dataset: ValidationDataset, root: Path | None = None) -> dict:
    root = root or project_root()
    c = dataset.conditions
    rows = []
    for point in dataset.points:
        request = CalculationRequest(
            device_id=dataset.device_id, model="M3",
            operating_point=OperatingPointInput(c["vdc_V"], point.id_A, point.tj_C,
                                                c["rg_on_ohm"], c["rg_off_ohm"], c["vg_on_V"], c["vg_off_V"], 0),
            return_waveforms=False, convergence_check=False,
        )
        result = calculate(request, root)
        rows.append({**asdict(point), "pred_eon_J": result.energy.eon_J, "pred_eoff_J": result.energy.eoff_J,
                     "ape_eon_pct": abs(result.energy.eon_J - point.eon_J) / point.eon_J * 100,
                     "ape_eoff_pct": abs(result.energy.eoff_J - point.eoff_J) / point.eoff_J * 100})
    holdout = [row for row in rows if row["split"] == "holdout"]
    return {"dataset_id": dataset.dataset_id, "source": dataset.source,
            "holdout_count": len(holdout), "calibration_count": len(rows) - len(holdout),
            "eon": _metrics([r["eon_J"] for r in holdout], [r["pred_eon_J"] for r in holdout]),
            "eoff": _metrics([r["eoff_J"] for r in holdout], [r["pred_eoff_J"] for r in holdout]),
            "rows": rows}


def parasitic_uncertainty(samples: int = 12, seed: int = 20260914, root: Path | None = None) -> dict:
    rng = np.random.default_rng(seed)
    outputs = []
    for _ in range(samples):
        p = ParasiticsInput(
            r_driver_on_ohm=max(0, rng.normal(0.5, 0.1)), r_driver_off_ohm=max(0, rng.normal(0.5, 0.1)),
            lg_H=max(0.2e-9, rng.normal(5e-9, 1e-9)), ls_H=max(0, rng.normal(5e-9, 1e-9)),
            lloop_H=max(0, rng.normal(20e-9, 4e-9)), rloop_ohm=max(0, rng.normal(0.05, 0.01)),
            loop_loss_fraction=float(np.clip(rng.normal(0.25, 0.05), 0, 1)),
        )
        request = CalculationRequest("C2M0025120D", "M3", OperatingPointInput(800, 40, 125, 5, 5), p,
                                     convergence_check=False)
        result = calculate(request, root)
        outputs.append((result.energy.eon_J, result.energy.eoff_J))
    values = np.asarray(outputs)
    return {"samples": samples, "seed": seed,
            "eon_J": {"mean": float(values[:, 0].mean()), "p05": float(np.percentile(values[:, 0], 5)), "p95": float(np.percentile(values[:, 0], 95))},
            "eoff_J": {"mean": float(values[:, 1].mean()), "p05": float(np.percentile(values[:, 1], 5)), "p95": float(np.percentile(values[:, 1], 95))},
            "note": "Monte Carlo covers stated parasitic tolerances only; it is not total model-form uncertainty."}


def run_default_validation(root: Path | None = None, uncertainty_samples: int = 12) -> dict:
    root = root or project_root()
    dataset = ValidationDataset.load(device_library_root(root) / "wolfspeed/C2M0025120D/validation/phase5_xml_holdout_v1.yaml")
    evaluation = evaluate_dataset(dataset, root)
    return {"status": "COMPLETE_WITH_EVIDENCE_LIMITATION", "model": "M3:m3_phase5_xml_shape_v1",
            "evaluation": evaluation, "uncertainty": parasitic_uncertainty(uncertainty_samples, root=root),
            "limitations": ["Calibration and holdout originate from the same manufacturer XML family.",
                            "No independent double-pulse measurements are available.",
                            "The manufacturer XML uses tabulated/formula loss data, not measured waveforms."]}
