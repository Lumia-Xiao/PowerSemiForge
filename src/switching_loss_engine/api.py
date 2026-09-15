from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from .devices import C2M0025120D, DeviceRegistry
from .models import CircuitParasitics, M0LossSurface, M1GateCharge, M2Segmented, M3VirtualDPT, OperatingPoint
from .schemas import CalculationRequest, CalculationResult, EnergyResult, ModelName, SolverStatus

ENGINE_VERSION = "0.6.0"
SCHEMA_VERSION = "1.0"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def device_library_root(root: Path | None = None) -> Path:
    if root is not None:
        root = Path(root)
        candidates = [root, root / "device_library", root / "src" / "powersemiforge" / "device_library"]
        for candidate in candidates:
            if (candidate / "wolfspeed" / "C2M0025120D" / "manifest.yaml").exists():
                return candidate
    bundled = Path(__file__).resolve().parents[1] / "powersemiforge" / "device_library"
    if not bundled.exists():
        raise FileNotFoundError(f"bundled device library not found: {bundled}")
    return bundled


def get_registry(root: Path | None = None) -> DeviceRegistry:
    registry = DeviceRegistry(device_library_root(root))
    registry.register("C2M0025120D", C2M0025120D)
    return registry


def available_devices(root: Path | None = None) -> list[str]:
    return get_registry(root).available()


def _legacy_inputs(request: CalculationRequest) -> tuple[OperatingPoint, CircuitParasitics]:
    o = request.operating_point
    p = request.parasitics
    return (
        OperatingPoint(o.vdc_V, o.id_A, o.tj_C, o.rg_on_ohm, o.rg_off_ohm, o.vg_on_V, o.vg_off_V, o.fsw_Hz),
        CircuitParasitics(p.r_driver_on_ohm, p.r_driver_off_ohm, p.lg_H, p.ls_H, p.lloop_H, p.rloop_ohm, p.loop_loss_fraction),
    )


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.to_dict(orient="records")


def calculate(request: CalculationRequest, root: Path | None = None) -> CalculationResult:
    request.validate()
    model_name = ModelName(request.model).value
    device = get_registry(root).create(request.device_id)
    op, parasitics = _legacy_inputs(request)
    calibration = device.load_calibration(model_name, request.calibration_id)
    start = perf_counter()
    waveforms = None
    components: dict[str, float] = {}

    if model_name == "M0":
        raw = M0LossSurface(device.data).predict(op)
        timing = {}
        stress = {}
        solver = SolverStatus(True, "ANALYTIC", "datasheet surface evaluated")
    elif model_name == "M1":
        raw = M1GateCharge(device.data, parasitics, calibration).predict(op)
        timing = {"current_rise": raw.t_current_rise_s, "voltage_fall": raw.t_voltage_fall_s,
                  "voltage_rise": raw.t_voltage_rise_s, "current_fall": raw.t_current_fall_s}
        stress = {"qgd_C": raw.qgd_dynamic_C, "qrr_C": raw.qrr_C}
        components = {"reverse_recovery": raw.E_rr_J, "output_capacitance": raw.Eoss_J}
        solver = SolverStatus(True, "ANALYTIC", "gate-charge equations evaluated")
    elif model_name == "M2":
        raw = M2Segmented(device.data, parasitics, calibration).predict(op)
        timing = {"current_rise": raw.t_ir_s, "voltage_fall": raw.t_vf_s,
                  "voltage_rise": raw.t_vr_s, "current_fall": raw.t_if_s}
        stress = {"didt_on_A_per_s": raw.didt_on_A_per_s, "didt_off_A_per_s": raw.didt_off_A_per_s,
                  "dvdt_on_V_per_s": raw.dvdt_on_V_per_s, "dvdt_off_V_per_s": raw.dvdt_off_V_per_s,
                  "vds_peak_V": raw.Vds_peak_off_V, "id_peak_A": raw.Id_peak_on_A, "qrr_C": raw.qrr_C}
        solver = SolverStatus(True, "ANALYTIC", "segmented equations evaluated")
    else:
        model = M3VirtualDPT(device.data, parasitics, calibration, request.time_step_s)
        if request.return_waveforms:
            raw, on, off = model.predict(op, return_waveforms=True, check_convergence=request.convergence_check)
            waveforms = {"turn_on": _records(on), "turn_off": _records(off)}
        else:
            raw = model.predict(op, return_waveforms=False, check_convergence=request.convergence_check)
        timing = {"current_rise": raw.tr_current_s, "voltage_fall": raw.tv_fall_s,
                  "voltage_rise": raw.tv_rise_s, "current_fall": raw.tf_current_s}
        stress = {"didt_max_A_per_s": raw.didt_max_A_per_s, "dvdt_max_V_per_s": raw.dvdt_max_V_per_s,
                  "vds_peak_V": raw.Vds_peak_V, "id_peak_A": raw.Id_peak_A}
        components = raw.components_J
        s = raw.solver_status
        rel_on = s.get("eon_relative_change")
        rel_off = s.get("eoff_relative_change")
        dt_ok = not s.get("checked") or (rel_on <= 0.08 and rel_off <= 0.08)
        converged = bool(s["converged"] and dt_ok)
        solver = SolverStatus(converged, "CONVERGED" if converged else "TIME_STEP_NOT_CONVERGED",
                              "all stages and time-step check passed" if converged else "inspect solver details",
                              s.get("time_step_s"), s.get("refinement_time_step_s"), rel_on, rel_off, s.get("stage_steps", {}))

    elapsed = perf_counter() - start
    warnings = []
    if model_name != "M0" and not (600 <= op.Vdc <= 800 and 12.56 <= op.Id <= 60):
        warnings.append("Operating point extends beyond the direct 600-800 V datasheet switching-energy evidence domain.")
    if calibration and asdict(request.parasitics) != calibration.reference_parasitics:
        warnings.append("Parasitics differ from the calibration reference; the fixed profile was not refit.")
    uncertainty_pct = {"M0": 18.0, "M1": 28.0, "M2": 26.0, "M3": 32.0}[model_name]
    return CalculationResult(
        schema_version=SCHEMA_VERSION, engine_version=ENGINE_VERSION,
        device_id=device.device_id, vendor=device.vendor, model=model_name,
        calibration_id=calibration.profile_id if calibration else None,
        input={"operating_point": asdict(request.operating_point), "parasitics": asdict(request.parasitics),
               "time_step_s": request.time_step_s},
        energy=EnergyResult(raw.Eon_J, raw.Eoff_J, raw.Esw_J, raw.Psw_W),
        timing_s=timing, stress=stress, components_J=components, solver=solver,
        uncertainty={"relative_95_pct": uncertainty_pct, "basis": "datasheet/XML holdout and model-form allowance"},
        provenance={"device_manifest": str(device.library_dir / "manifest.yaml"),
                    "calculation_seconds": elapsed, "calibration_source": calibration.source if calibration else None},
        warnings=warnings, waveforms=waveforms,
    )
