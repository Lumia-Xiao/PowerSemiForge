from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from .device_data import C2M0025120DData, OperatingPoint, CircuitParasitics
from ..calibration import CalibrationProfile
from ..exceptions import CalibrationError


@dataclass
class M1Result:
    Eon_raw_J: float
    Eoff_raw_J: float
    Eon_J: float
    Eoff_J: float
    Esw_J: float
    Psw_W: float
    t_current_rise_s: float
    t_voltage_fall_s: float
    t_voltage_rise_s: float
    t_current_fall_s: float
    qgd_dynamic_C: float
    qrr_C: float
    E_rr_J: float
    Eoss_J: float
    scale_on: float
    scale_off: float
    note: str

    def as_dict(self): return asdict(self)


class M1GateCharge:
    """Gate-charge semi-analytical switching-loss model.

    Uses:
    - Fig.7 transfer characteristic to estimate plateau Vgs for requested current.
    - Fig.12 Vgs(Qg) to integrate current-rise / current-fall gate charge time.
    - Fig.18 Crss(V) shape, anchored to table Qgd=71.5 nC, for voltage transition time.
    - Two datasheet Qrr points for a simple recovery model.
    - Fig.16 Eoss(V) as a separate turn-on bookkeeping term.

    A single fixed multiplicative calibration at the datasheet reference point is applied
    to raw Eon/Eoff. It is NOT refit at each operating point.
    """
    def __init__(self, data: C2M0025120DData, parasitics: CircuitParasitics | None = None,
                 calibration: CalibrationProfile | None = None):
        self.d = data
        self.p = parasitics or CircuitParasitics()
        self.calibration = calibration

    def _gate_charge_time(self, v_start: float, v_end: float, Rtotal: float, Vdrive: float, n=500) -> float:
        # Integrate dt = R * dQ / (Vdrive - Vgs(Q)) with correct sign for charge/discharge.
        q0 = self.d.q_from_vgs(v_start)
        q1 = self.d.q_from_vgs(v_end)
        q = np.linspace(q0, q1, n)
        vgs = np.array([self.d.vgs_from_q(x) for x in q])
        denom = np.abs(Vdrive - vgs)
        denom = np.maximum(denom, 0.2)  # avoid singularity at final rail; model stops before exact rail
        return float(abs(np.trapezoid(Rtotal / denom, q)))

    def _raw(self, op: OperatingPoint):
        ron = self.d.rds_on(op.Tj)
        von = max(op.Id * ron, 0.05)
        vpl = self.d.inverse_transfer_vgs(op.Id, op.Tj)
        vth = self.d.vth(op.Tj)
        R_on = self.d.RG_INT + op.Rg_ext_on + self.p.R_driver_on
        R_off = self.d.RG_INT + op.Rg_off + self.p.R_driver_off

        # Current rise / fall based on extracted gate-charge curve.
        t_ir = self._gate_charge_time(vth, vpl, R_on, op.Vg_on)
        t_if = self._gate_charge_time(vpl, vth, R_off, op.Vg_off)

        qgd = self.d.dynamic_qgd(op.Vdc, op.Id, op.Tj)
        ig_m_on = max((op.Vg_on - vpl) / R_on, 1e-3)
        ig_m_off = max((vpl - op.Vg_off) / R_off, 1e-3)
        t_vf = qgd / ig_m_on
        t_vr = qgd / ig_m_off

        # Overlap estimates. Voltage/current are approximated as linear in each stage.
        e_on_ir = 0.5 * op.Vdc * op.Id * t_ir
        e_on_vf = 0.5 * (op.Vdc + von) * op.Id * t_vf
        e_off_vr = 0.5 * (op.Vdc + von) * op.Id * t_vr
        e_off_if = 0.5 * op.Vdc * op.Id * t_if

        didt_on = op.Id / max(t_ir, 1e-12)
        qrr = self.d.qrr(didt_on, op.Id)
        e_rr = op.Vdc * qrr
        eoss = self.d.eoss(op.Vdc)

        eon = e_on_ir + e_on_vf + e_rr + eoss
        eoff = e_off_vr + e_off_if
        return dict(Eon=eon, Eoff=eoff, t_ir=t_ir, t_vf=t_vf, t_vr=t_vr, t_if=t_if,
                    qgd=qgd, qrr=qrr, e_rr=e_rr, eoss=eoss)

    def predict(self, op: OperatingPoint, calibrated=True) -> M1Result:
        raw = self._raw(op)
        if calibrated and self.calibration is None:
            raise CalibrationError("M1 requires an explicit CalibrationProfile")
        son = self.calibration.factor(op.Id, op.Tj, "Eon") if calibrated else 1.0
        soff = self.calibration.factor(op.Id, op.Tj, "Eoff") if calibrated else 1.0
        eon, eoff = raw["Eon"]*son, raw["Eoff"]*soff
        return M1Result(
            Eon_raw_J=raw["Eon"], Eoff_raw_J=raw["Eoff"],
            Eon_J=eon, Eoff_J=eoff, Esw_J=eon+eoff, Psw_W=(eon+eoff)*op.fsw,
            t_current_rise_s=raw["t_ir"], t_voltage_fall_s=raw["t_vf"],
            t_voltage_rise_s=raw["t_vr"], t_current_fall_s=raw["t_if"],
            qgd_dynamic_C=raw["qgd"], qrr_C=raw["qrr"], E_rr_J=raw["e_rr"], Eoss_J=raw["eoss"],
            scale_on=son, scale_off=soff,
            note="Gate-charge model with an explicitly loaded, versioned calibration profile."
        )
