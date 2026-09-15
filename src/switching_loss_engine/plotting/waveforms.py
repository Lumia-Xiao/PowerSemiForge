from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..schemas import CalculationResult


def plot_waveforms(result: CalculationResult, path: str | Path) -> Path:
    if not result.waveforms:
        raise ValueError("result has no waveforms; set return_waveforms=True")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for column, label, axis in [("Vds_V", "Vds (V)", axes[0, 0]), ("Id_A", "Id (A)", axes[0, 1]),
                                ("Vgs_V", "Vgs (V)", axes[1, 0]), ("P_W", "Instantaneous power (W)", axes[1, 1])]:
        for event, records in result.waveforms.items():
            frame = pd.DataFrame(records)
            axis.plot(frame["t_s"] * 1e9, frame[column], label=event.replace("_", " "))
        axis.set_xlabel("Local event time (ns)")
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.3)
        axis.legend()
    fig.suptitle(f"{result.device_id} {result.model} switching waveforms")
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path

