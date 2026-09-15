from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from .device_data import C2M0025120DData, OperatingPoint, CircuitParasitics
from ..calibration import CalibrationProfile
from ..exceptions import CalibrationError


@dataclass
class M2Result:
    Eon_raw_J: float
    Eoff_raw_J: float
    Eon_J: float
    Eoff_J: float
    Esw_J: float
    Psw_W: float
    t_ir_s: float
    t_vf_s: float
    t_vr_s: float
    t_if_s: float
    didt_on_A_per_s: float
    didt_off_A_per_s: float
    dvdt_on_V_per_s: float
    dvdt_off_V_per_s: float
    Vds_peak_off_V: float
    Id_peak_on_A: float
    qrr_C: float
    scale_on: float
    scale_off: float
    note: str

    def as_dict(self): return asdict(self)


class M2Segmented:
    """Segmented quasi-analytical model with explicit parasitics.

    This is an engineering implementation inspired by the stage-wise analytical models
    discussed previously. It is NOT a verbatim implementation of Hu/Qian/Roy equations.

    Main additions over M1:
    - common-source inductance feedback in current-rise/current-fall timing;
    - gate inductance represented as a stage-frequency effective impedance correction;
    - power-loop inductance used for turn-off overshoot and loop-energy bookkeeping;
    - nonlinear Cgd(V) shape anchored to datasheet Qgd.
    """
    def __init__(self, data: C2M0025120DData, parasitics: CircuitParasitics | None = None,
                 calibration: CalibrationProfile | None = None):
        self.d = data
        self.p = parasitics or CircuitParasitics()
        self.calibration = calibration

    def _current_stage_time(self, op: OperatingPoint, turn_on: bool, n=600):
        vth = self.d.vth(op.Tj)
        vpl = self.d.inverse_transfer_vgs(op.Id, op.Tj)
        if turn_on:
            va, vb, vdrive = vth, vpl, op.Vg_on
            Rbase = self.d.RG_INT + op.Rg_ext_on + self.p.R_driver_on
        else:
            va, vb, vdrive = vpl, vth, op.Vg_off
            Rbase = self.d.RG_INT + op.Rg_off + self.p.R_driver_off

        v = np.linspace(va, vb, n)
        ciss = np.array([sum(self.d.capacitances(op.Vdc)[:2]) for _ in v])  # Cgs+Cgd
        gm = np.array([self.d.transfer_gm(x, op.Tj) for x in v])

        # First estimate without Lg, then convert Lg/t_stage to an effective impedance.
        reff0 = Rbase + self.p.Ls * gm / np.maximum(ciss, 1e-15)
        den0 = np.maximum(np.abs(vdrive - v), 0.2)
        t0 = abs(np.trapezoid(reff0 * ciss / den0, v))
        Rlg = self.p.Lg / max(t0, 0.5e-9)
        reff = reff0 + Rlg
        t = abs(np.trapezoid(reff * ciss / den0, v))
        return float(t), float(vpl)

    def _miller_time(self, op: OperatingPoint, vpl: float, turn_on: bool):
        qgd = self.d.dynamic_qgd(op.Vdc, op.Id, op.Tj)
        if turn_on:
            Rbase = self.d.RG_INT + op.Rg_ext_on + self.p.R_driver_on
            dv = max(op.Vg_on - vpl, 0.2)
        else:
            Rbase = self.d.RG_INT + op.Rg_off + self.p.R_driver_off
            dv = max(vpl - op.Vg_off, 0.2)
        t0 = qgd * Rbase / dv
        Rlg = self.p.Lg / max(t0, 0.5e-9)
        return qgd * (Rbase + Rlg) / dv

    def _raw(self, op: OperatingPoint):
        ron = self.d.rds_on(op.Tj)
        von = max(op.Id * ron, 0.05)
        t_ir, vpl = self._current_stage_time(op, True)
        t_if, _ = self._current_stage_time(op, False)
        t_vf = self._miller_time(op, vpl, True)
        t_vr = self._miller_time(op, vpl, False)

        didt_on = op.Id / max(t_ir, 1e-12)
        didt_off = op.Id / max(t_if, 1e-12)
        dvdt_on = (op.Vdc - von) / max(t_vf, 1e-12)
        dvdt_off = (op.Vdc - von) / max(t_vr, 1e-12)

        qrr = self.d.qrr(didt_on, op.Id)
        trr = self.d.trr(didt_on)
        irr_peak = 2.0 * qrr / max(trr, 1e-12)
        id_peak = op.Id + irr_peak
        vpeak = min(self.d.VDS_RATED, op.Vdc + self.p.Lloop * didt_off)

        # Stage-overlap energy.
        e_on_ir = 0.5 * op.Vdc * op.Id * t_ir
        e_on_vf = 0.5 * (op.Vdc + von) * op.Id * t_vf
        e_rr = op.Vdc * qrr
        eoss = self.d.eoss(op.Vdc)

        e_off_vr = 0.5 * (op.Vdc + von) * op.Id * t_vr
        e_off_if = 0.25 * (op.Vdc + vpeak) * op.Id * t_if

        # Only a configurable fraction of loop magnetic energy is assigned to semiconductor loss.
        eloop_on = self.p.loop_loss_fraction * 0.5 * self.p.Lloop * max(id_peak**2 - op.Id**2, 0.0)
        eloop_off = self.p.loop_loss_fraction * 0.5 * self.p.Lloop * op.Id**2

        eon = e_on_ir + e_on_vf + e_rr + eoss + eloop_on
        eoff = e_off_vr + e_off_if + eloop_off
        return dict(Eon=eon, Eoff=eoff, t_ir=t_ir, t_vf=t_vf, t_vr=t_vr, t_if=t_if,
                    didt_on=didt_on, didt_off=didt_off, dvdt_on=dvdt_on, dvdt_off=dvdt_off,
                    vpeak=vpeak, id_peak=id_peak, qrr=qrr)

    def predict(self, op: OperatingPoint, calibrated=True) -> M2Result:
        raw = self._raw(op)
        if calibrated and self.calibration is None:
            raise CalibrationError("M2 requires an explicit CalibrationProfile")
        son = self.calibration.factor(op.Id, op.Tj, "Eon") if calibrated else 1.0
        soff = self.calibration.factor(op.Id, op.Tj, "Eoff") if calibrated else 1.0
        eon, eoff = raw["Eon"]*son, raw["Eoff"]*soff
        return M2Result(
            Eon_raw_J=raw["Eon"], Eoff_raw_J=raw["Eoff"],
            Eon_J=eon, Eoff_J=eoff, Esw_J=eon+eoff, Psw_W=(eon+eoff)*op.fsw,
            t_ir_s=raw["t_ir"], t_vf_s=raw["t_vf"], t_vr_s=raw["t_vr"], t_if_s=raw["t_if"],
            didt_on_A_per_s=raw["didt_on"], didt_off_A_per_s=raw["didt_off"],
            dvdt_on_V_per_s=raw["dvdt_on"], dvdt_off_V_per_s=raw["dvdt_off"],
            Vds_peak_off_V=raw["vpeak"], Id_peak_on_A=raw["id_peak"], qrr_C=raw["qrr"],
            scale_on=son, scale_off=soff,
            note="Segmented model; parasitics are explicit inputs and calibration is fixed/versioned."
        )
