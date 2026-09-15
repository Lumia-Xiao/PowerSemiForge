from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd

from ..calibration import CalibrationProfile
from ..exceptions import CalibrationError
from .device_data import C2M0025120DData, CircuitParasitics, OperatingPoint


@dataclass
class M3Result:
    Eon_raw_J: float
    Eoff_raw_J: float
    Eon_J: float
    Eoff_J: float
    Esw_J: float
    Psw_W: float
    tr_current_s: float
    tf_current_s: float
    tv_fall_s: float
    tv_rise_s: float
    didt_max_A_per_s: float
    dvdt_max_V_per_s: float
    Vds_peak_V: float
    Id_peak_A: float
    scale_on: float
    scale_off: float
    solver_status: dict
    components_J: dict
    note: str

    def as_dict(self):
        return asdict(self)


class M3VirtualDPT:
    """Stage-continuous reduced-order double-pulse transient solver.

    Lg and Ls appear in the gate differential equation. Lloop and Rloop
    appear in the commutation/overshoot equations and loop-energy bookkeeping.
    Calibration is loaded once from a versioned profile and never recomputed
    when parasitics or the operating point change.
    """

    def __init__(
        self,
        data: C2M0025120DData,
        parasitics: CircuitParasitics | None = None,
        calibration: CalibrationProfile | None = None,
        dt: float = 0.1e-9,
        max_stage_steps: int = 200_000,
    ):
        self.d = data
        self.p = parasitics or CircuitParasitics()
        self.calibration = calibration
        self.dt = float(dt)
        self.max_stage_steps = int(max_stage_steps)

    @staticmethod
    def _triangular_pulse(t: np.ndarray, duration: float, area: float) -> np.ndarray:
        if duration <= 0 or area <= 0:
            return np.zeros_like(t)
        peak = 2.0 * area / duration
        mid = duration / 2.0
        y = np.where(t <= mid, peak * t / max(mid, 1e-15), peak * (duration - t) / max(mid, 1e-15))
        return np.maximum(y, 0.0)

    def _cgd_scale(self, op: OperatingPoint) -> float:
        von = max(op.Id * self.d.rds_on(op.Tj), 0.05)
        raw_q = self.d.cgd_integral(von, op.Vdc)
        return self.d.dynamic_qgd(op.Vdc, op.Id, op.Tj) / max(raw_q, 1e-15)

    def _gate_step(self, ig: float, vgs: float, vdrive: float, rg: float, lg: float,
                   ciss: float, ls_feedback_V: float = 0.0) -> tuple[float, float]:
        # Backward-Euler resistance term damps the sub-nanosecond Lg state.
        ig_new = (ig + self.dt * (vdrive - vgs - ls_feedback_V) / lg) / (1.0 + self.dt * rg / lg)
        vgs_new = vgs + self.dt * ig_new / max(ciss, 1e-15)
        lo, hi = sorted((vdrive, vgs))
        return float(ig_new), float(np.clip(vgs_new, lo - 0.25, hi + 0.25))

    @staticmethod
    def _stage_gradient(frame: pd.DataFrame, stage: str, column: str) -> float:
        selected = frame[frame["stage"] == stage]
        if len(selected) < 3:
            return 0.0
        return float(np.max(np.abs(np.gradient(selected[column].to_numpy(), selected["t_s"].to_numpy()))))

    def _simulate_turn_on(self, op: OperatingPoint) -> dict:
        dt = self.dt
        p = self.p
        rg = self.d.RG_INT + op.Rg_ext_on + p.R_driver_on
        lg = max(p.Lg, 0.2e-9)
        vth = self.d.vth(op.Tj)
        vpl = self.d.inverse_transfer_vgs(op.Id, op.Tj)
        von = max(op.Id * self.d.rds_on(op.Tj), 0.05)
        cgd_scale = self._cgd_scale(op)
        rows: list[tuple] = []
        counts: dict[str, int] = {}
        t, vgs, vds, ids, ig, irr = 0.0, op.Vg_off, op.Vdc, 0.0, 0.0, 0.0

        def add(stage: str) -> None:
            counts[stage] = counts.get(stage, 0) + 1
            rows.append((t, stage, vgs, vds, ids, ig, irr, vds * ids))

        add("initial")
        reached = {}
        for _ in range(self.max_stage_steps):
            cgs, cgd, _ = self.d.capacitances(vds)
            ig, vgs = self._gate_step(ig, vgs, op.Vg_on, rg, lg, cgs + cgd)
            t += dt
            add("gate_delay")
            if vgs >= vth:
                reached["gate_delay"] = True
                break
        else:
            reached["gate_delay"] = False

        t0 = t
        last_ids = ids
        for _ in range(self.max_stage_steps):
            cgs, cgd, _ = self.d.capacitances(vds)
            ciss = cgs + cgd
            gm = self.d.transfer_gm(vgs, op.Tj)
            did_est = gm * ig / max(ciss, 1e-15)
            ig, vgs = self._gate_step(ig, vgs, op.Vg_on, rg, lg, ciss, p.Ls * did_est)
            ids = min(op.Id, max(0.0, self.d.channel_current(vgs, max(vds, 1.0), op.Tj)))
            didt = (ids - last_ids) / dt
            # Rloop is a real series drop; Lloop opposes commutation current change.
            vds = float(np.clip(op.Vdc - p.Rloop * ids - p.Lloop * max(didt, 0.0), von, op.Vdc))
            last_ids = ids
            t += dt
            add("current_rise")
            if ids >= 0.999 * op.Id:
                reached["current_rise"] = True
                break
        else:
            reached["current_rise"] = False
        tr_current = t - t0
        didt_char = op.Id / max(tr_current, 1e-12)

        qrr = self.d.qrr(didt_char, op.Id)
        trr = self.d.trr(didt_char)
        tau = np.arange(max(2, int(math.ceil(trr / dt)))) * dt
        irr_values = self._triangular_pulse(tau, trr, qrr)
        last_irr = 0.0
        for value in irr_values:
            irr = float(value)
            ids = op.Id + irr
            dirr_dt = (irr - last_irr) / dt
            vds = float(np.clip(op.Vdc - p.Rloop * ids - p.Lloop * max(dirr_dt, 0.0), von, op.Vdc))
            last_irr = irr
            t += dt
            add("reverse_recovery")
        reached["reverse_recovery"] = True

        irr = 0.0
        ids = op.Id
        vgs = vpl
        t0 = t
        for _ in range(self.max_stage_steps):
            cgd = self.d.capacitances(vds)[1] * cgd_scale
            ig = max((op.Vg_on - vpl) / rg, 1e-3)
            vds = max(von, vds - dt * ig / max(cgd, 1e-15))
            t += dt
            add("voltage_fall")
            if vds <= von + 0.02:
                reached["voltage_fall"] = True
                break
        else:
            reached["voltage_fall"] = False
        tv_fall = t - t0

        frame = pd.DataFrame(rows, columns=["t_s", "stage", "Vgs_V", "Vds_V", "Id_A", "Ig_A", "Irr_A", "P_W"])
        overlap = float(np.trapezoid(frame["P_W"], frame["t_s"]))
        loop = p.loop_loss_fraction * 0.5 * p.Lloop * max(float(frame["Id_A"].max()) ** 2 - op.Id ** 2, 0.0)
        return {"energy": overlap + loop, "overlap": overlap, "loop": loop, "waveform": frame,
                "tr": tr_current, "tv": tv_fall, "reached": reached, "counts": counts}

    def _simulate_turn_off(self, op: OperatingPoint) -> dict:
        dt = self.dt
        p = self.p
        rg = self.d.RG_INT + op.Rg_off + p.R_driver_off
        lg = max(p.Lg, 0.2e-9)
        vth = self.d.vth(op.Tj)
        vpl = self.d.inverse_transfer_vgs(op.Id, op.Tj)
        von = max(op.Id * self.d.rds_on(op.Tj), 0.05)
        cgd_scale = self._cgd_scale(op)
        rows: list[tuple] = []
        counts: dict[str, int] = {}
        t, vgs, vds, ids, ig = 0.0, op.Vg_on, von, op.Id, 0.0

        def add(stage: str) -> None:
            counts[stage] = counts.get(stage, 0) + 1
            rows.append((t, stage, vgs, vds, ids, ig, vds * ids))

        add("initial")
        reached = {}
        for _ in range(self.max_stage_steps):
            cgs, cgd, _ = self.d.capacitances(vds)
            ig, vgs = self._gate_step(ig, vgs, op.Vg_off, rg, lg, cgs + cgd)
            t += dt
            add("gate_discharge")
            if vgs <= vpl:
                reached["gate_discharge"] = True
                break
        else:
            reached["gate_discharge"] = False

        vgs = vpl
        t0 = t
        for _ in range(self.max_stage_steps):
            cgd = self.d.capacitances(vds)[1] * cgd_scale
            ig = -max((vpl - op.Vg_off) / rg, 1e-3)
            vds = min(op.Vdc, vds + dt * abs(ig) / max(cgd, 1e-15))
            t += dt
            add("voltage_rise")
            if vds >= op.Vdc - 0.02:
                reached["voltage_rise"] = True
                break
        else:
            reached["voltage_rise"] = False
        tv_rise = t - t0

        t0 = t
        last_ids = ids
        for _ in range(self.max_stage_steps):
            cgs, cgd, _ = self.d.capacitances(op.Vdc)
            ciss = cgs + cgd
            gm = self.d.transfer_gm(vgs, op.Tj)
            did_est = gm * ig / max(ciss, 1e-15)
            ig, vgs = self._gate_step(ig, vgs, op.Vg_off, rg, lg, ciss, p.Ls * did_est)
            ids = min(op.Id, max(0.0, self.d.channel_current(vgs, op.Vdc, op.Tj)))
            didt = (ids - last_ids) / dt
            vds = min(self.d.VDS_RATED, op.Vdc + p.Rloop * ids + p.Lloop * abs(min(didt, 0.0)))
            last_ids = ids
            t += dt
            add("current_fall")
            if ids <= max(0.01 * op.Id, 0.05) or vgs <= vth:
                reached["current_fall"] = True
                break
        else:
            reached["current_fall"] = False
        tf_current = t - t0

        frame = pd.DataFrame(rows, columns=["t_s", "stage", "Vgs_V", "Vds_V", "Id_A", "Ig_A", "P_W"])
        overlap = float(np.trapezoid(frame["P_W"], frame["t_s"]))
        loop = p.loop_loss_fraction * 0.5 * p.Lloop * op.Id ** 2
        return {"energy": overlap + loop, "overlap": overlap, "loop": loop, "waveform": frame,
                "tf": tf_current, "tv": tv_rise, "reached": reached, "counts": counts}

    def _raw(self, op: OperatingPoint) -> dict:
        on = self._simulate_turn_on(op)
        off = self._simulate_turn_off(op)
        won, woff = on["waveform"], off["waveform"]
        reached = {f"on_{k}": v for k, v in on["reached"].items()} | {f"off_{k}": v for k, v in off["reached"].items()}
        finite = all(np.isfinite(df[["t_s", "Vgs_V", "Vds_V", "Id_A", "Ig_A", "P_W"]].to_numpy()).all() for df in (won, woff))
        continuous = bool((won["t_s"].diff().dropna() > 0).all() and (woff["t_s"].diff().dropna() > 0).all())
        converged = all(reached.values()) and finite and continuous
        return {
            "Eon": on["energy"], "Eoff": off["energy"], "won": won, "woff": woff,
            "trc": on["tr"], "tfc": off["tf"], "tvf": on["tv"], "tvr": off["tv"],
            "didt_max": max(self._stage_gradient(won, "current_rise", "Id_A"), self._stage_gradient(woff, "current_fall", "Id_A")),
            "dvdt_max": max(self._stage_gradient(won, "voltage_fall", "Vds_V"), self._stage_gradient(woff, "voltage_rise", "Vds_V")),
            "vpeak": float(max(won["Vds_V"].max(), woff["Vds_V"].max())),
            "idpeak": float(max(won["Id_A"].max(), woff["Id_A"].max())),
            "components": {"turn_on_overlap": on["overlap"], "turn_on_loop": on["loop"], "turn_off_overlap": off["overlap"], "turn_off_loop": off["loop"]},
            "status": {"converged": converged, "reached": reached, "finite": finite, "continuous_time": continuous, "stage_steps": on["counts"] | {f"off_{k}": v for k, v in off["counts"].items()}},
        }

    def predict(self, op: OperatingPoint, calibrated: bool = True, return_waveforms: bool = False,
                check_convergence: bool = False):
        if calibrated and self.calibration is None:
            raise CalibrationError("M3 requires an explicit CalibrationProfile")
        raw = self._raw(op)
        convergence = {"checked": False, "eon_relative_change": None, "eoff_relative_change": None, "refinement_time_step_s": None}
        if check_convergence:
            refined_solver = M3VirtualDPT(self.d, self.p, self.calibration, self.dt / 2.0, self.max_stage_steps * 2)
            refined = refined_solver._raw(op)
            convergence = {
                "checked": True,
                "eon_relative_change": abs(refined["Eon"] - raw["Eon"]) / max(abs(refined["Eon"]), 1e-15),
                "eoff_relative_change": abs(refined["Eoff"] - raw["Eoff"]) / max(abs(refined["Eoff"]), 1e-15),
                "refinement_time_step_s": self.dt / 2.0,
            }
            raw = refined
        son = self.calibration.factor(op.Id, op.Tj, "Eon") if calibrated else 1.0
        soff = self.calibration.factor(op.Id, op.Tj, "Eoff") if calibrated else 1.0
        eon, eoff = raw["Eon"] * son, raw["Eoff"] * soff
        status = raw["status"] | convergence | {"time_step_s": self.dt / (2.0 if check_convergence else 1.0)}
        result = M3Result(
            Eon_raw_J=raw["Eon"], Eoff_raw_J=raw["Eoff"], Eon_J=eon, Eoff_J=eoff,
            Esw_J=eon + eoff, Psw_W=(eon + eoff) * op.fsw,
            tr_current_s=raw["trc"], tf_current_s=raw["tfc"], tv_fall_s=raw["tvf"], tv_rise_s=raw["tvr"],
            didt_max_A_per_s=raw["didt_max"], dvdt_max_V_per_s=raw["dvdt_max"],
            Vds_peak_V=raw["vpeak"], Id_peak_A=raw["idpeak"], scale_on=son, scale_off=soff,
            solver_status=status, components_J=raw["components"],
            note="Stage-continuous virtual DPT with explicit parasitics and fixed versioned calibration.",
        )
        return (result, raw["won"], raw["woff"]) if return_waveforms else result

