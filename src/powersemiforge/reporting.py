from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def build_report(results_csv: str | Path, output_dir: str | Path) -> dict:
    results_csv = Path(results_csv)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(results_csv)
    required = {"device_id", "model", "id_A", "tj_C", "eon_J", "eoff_J", "esw_J"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"results CSV missing columns: {sorted(missing)}")
    summary = frame.groupby(["device_id", "model"], as_index=False).agg(
        points=("esw_J", "size"), eon_mean_J=("eon_J", "mean"), eoff_mean_J=("eoff_J", "mean"),
        esw_min_J=("esw_J", "min"), esw_max_J=("esw_J", "max"),
        calculation_seconds=("calculation_seconds", "sum"),
    )
    summary.to_csv(output_dir / "summary.csv", index=False)
    figures = []
    for (device, model), group in frame.groupby(["device_id", "model"]):
        fig, ax = plt.subplots(figsize=(7.5, 4.8), constrained_layout=True)
        for temperature, subset in group.groupby("tj_C"):
            subset = subset.sort_values("id_A")
            ax.plot(subset["id_A"], subset["eon_J"] * 1e3, marker="o", label=f"Eon, {temperature:g} C")
            ax.plot(subset["id_A"], subset["eoff_J"] * 1e3, marker="s", linestyle="--", label=f"Eoff, {temperature:g} C")
        ax.set(xlabel="Switching current (A)", ylabel="Energy (mJ)", title=f"{device} - {model}")
        ax.grid(True, alpha=0.3)
        ax.legend()
        output = output_dir / f"{device}-{model}-energy.png"
        fig.savefig(output, dpi=180)
        plt.close(fig)
        figures.append(str(output))
    report = {"schema_version": "1.0", "source": str(results_csv.resolve()),
              "rows": len(frame), "groups": len(summary), "figures": figures,
              "converged_fraction": float(frame["solver_converged"].mean()) if "solver_converged" in frame else None}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

