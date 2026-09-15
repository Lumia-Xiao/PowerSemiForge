from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict
from functools import lru_cache
import math
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq


@dataclass(frozen=True)
class OperatingPoint:
    Vdc: float
    Id: float
    Tj: float = 25.0
    Rg_ext_on: float = 2.5
    Rg_ext_off: float | None = None
    Vg_on: float = 20.0
    Vg_off: float = -5.0
    fsw: float = 100e3

    @property
    def Rg_off(self) -> float:
        return self.Rg_ext_on if self.Rg_ext_off is None else self.Rg_ext_off


@dataclass(frozen=True)
class CircuitParasitics:
    # These are CIRCUIT inputs, not guaranteed device datasheet values.
    R_driver_on: float = 0.5      # ohm, example assumption
    R_driver_off: float = 0.5     # ohm, example assumption
    Lg: float = 5e-9              # H, example assumption
    Ls: float = 5e-9              # H, example assumption
    Lloop: float = 20e-9          # H, example assumption
    Rloop: float = 0.05           # ohm, example assumption
    loop_loss_fraction: float = 0.25


class Curve1D:
    def __init__(self, x, y, log_y=False):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]
        order = np.argsort(x)
        x, y = x[order], y[order]
        x, unique_idx = np.unique(x, return_index=True)
        y = y[unique_idx]
        self.x = x
        self.y = y
        self.log_y = log_y
        self._interp = PchipInterpolator(x, np.log10(y) if log_y else y, extrapolate=False)

    @property
    def xmin(self): return float(self.x.min())
    @property
    def xmax(self): return float(self.x.max())

    def __call__(self, xq):
        arr = np.asarray(xq, dtype=float)
        val = self._interp(arr)
        if self.log_y:
            val = 10.0 ** val
        if np.ndim(xq) == 0:
            return float(val)
        return val


class C2M0025120DData:
    """Data access layer for the vector-extracted C2M0025120D curves.

    All hard-coded scalar constants below are from the uploaded Wolfspeed datasheet.
    The digitized CSVs are used for shape/interpolation; no hidden web data are used.
    """

    # Scalar datasheet anchors
    VDS_RATED = 1200.0
    RG_INT = 1.0
    QGS = 46e-9
    QGD = 71.5e-9
    QG = 194e-9
    RDS25 = 25e-3
    RDS150 = 41e-3
    VTH_TABLE_25 = 2.6
    VTH_TABLE_150 = 2.3

    # Reference switching test (body diode commutation)
    REF_V = 800.0
    REF_I = 50.0
    REF_T = 25.0
    REF_RG = 2.5
    REF_VG_ON = 20.0
    REF_VG_OFF = -5.0
    REF_EON = 2.18e-3
    REF_EOFF = 0.68e-3
    REF_TD_ON = 15e-9
    REF_TR = 58e-9
    REF_TD_OFF = 33e-9
    REF_TF = 17e-9

    # Reverse-recovery anchors (body diode, 25 C, 800 V, 50 A)
    QRR_1 = 487e-9
    DIDT_1 = 2180e6  # A/s
    TRR_1 = 33e-9
    IRRM_1 = 24.0
    QRR_2 = 386e-9
    DIDT_2 = 1320e6
    TRR_2 = 67e-9
    IRRM_2 = 15.0

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self._load()

    def _csv(self, name):
        return pd.read_csv(self.data_dir / name)

    def _load(self):
        # Transfer curves
        d = self._csv("Fig07_transfer_characteristics.csv")
        self.transfer_curves: Dict[float, Curve1D] = {
            -55.0: Curve1D(d["VGS_V"], d["IDS_Tj_-55C_A"]),
            25.0: Curve1D(d["VGS_V"], d["IDS_Tj_25C_A"]),
            150.0: Curve1D(d["VGS_V"], d["IDS_Tj_150C_A"]),
        }

        d = self._csv("Fig11_threshold_voltage_vs_temperature.csv")
        self.vth_curve = Curve1D(d["Tj_C"], d["Vth_V"])

        d = self._csv("Fig12_gate_charge_characteristics.csv")
        self.vgs_q_curve = Curve1D(d["Qg_nC"].to_numpy() * 1e-9, d["VGS_V"])
        # Monotonic inverse over the valid portion
        q = d["Qg_nC"].to_numpy(dtype=float) * 1e-9
        v = d["VGS_V"].to_numpy(dtype=float)
        mask = np.isfinite(q) & np.isfinite(v)
        q, v = q[mask], v[mask]
        # VGS(Q) is monotonic in this datasheet curve, so inverse is safe after unique V filtering.
        vu, idx = np.unique(v, return_index=True)
        self.q_vgs_curve = Curve1D(vu, q[idx])

        d = self._csv("Fig16_output_capacitor_stored_energy.csv")
        self.eoss_curve = Curve1D(d["VDS_V"], d["Eoss_uJ"].to_numpy() * 1e-6)

        d17 = self._csv("Fig17_capacitances_vs_VDS_0_200V.csv")
        d18 = self._csv("Fig18_capacitances_vs_VDS_0_1200V.csv")
        # Use Fig.17 below 200 V for low-voltage detail and Fig.18 above 200 V.
        self.cap17 = {k: Curve1D(d17["VDS_V"], d17[k], log_y=True)
                      for k in ["Ciss_pF", "Coss_pF", "Crss_pF"]}
        self.cap18 = {k: Curve1D(d18["VDS_V"], d18[k], log_y=True)
                      for k in ["Ciss_pF", "Coss_pF", "Crss_pF"]}

        self.energy_600 = self._load_energy_curve("Fig23_switching_energy_vs_IDS_600V.csv")
        self.energy_800 = self._load_energy_curve("Fig24_switching_energy_vs_IDS_800V.csv")

        d = self._csv("Fig26_switching_energy_vs_Tj.csv")
        self.temp_energy = {
            "Eon_body": Curve1D(d["Tj_C"], d["Eon_body_mJ"].to_numpy() * 1e-3),
            "Eoff_body": Curve1D(d["Tj_C"], d["Eoff_body_mJ"].to_numpy() * 1e-3),
            "Eon_schottky": Curve1D(d["Tj_C"], d["Eon_schottky_mJ"].to_numpy() * 1e-3),
            "Eoff_schottky": Curve1D(d["Tj_C"], d["Eoff_schottky_mJ"].to_numpy() * 1e-3),
        }

        d = self._csv("Fig27_switching_times_vs_Rg.csv")
        self.rg_times = {
            "td_on": Curve1D(d["Rg_ext_Ohm"], d["td_on_ns"].to_numpy() * 1e-9),
            "tr": Curve1D(d["Rg_ext_Ohm"], d["tr_ns"].to_numpy() * 1e-9),
            "td_off": Curve1D(d["Rg_ext_Ohm"], d["td_off_ns"].to_numpy() * 1e-9),
            "tf": Curve1D(d["Rg_ext_Ohm"], d["tf_ns"].to_numpy() * 1e-9),
        }

        # Fig.25 is retained only as diagnostic due to the extracted Etotal inconsistency.
        d = self._csv("Fig25_switching_energy_vs_Rg.csv")
        self.rg_energy_diag = {
            "Eon": Curve1D(d["Rg_ext_Ohm"], d["Eon_mJ"].to_numpy() * 1e-3),
            "Eoff": Curve1D(d["Rg_ext_Ohm"], d["Eoff_mJ"].to_numpy() * 1e-3),
            "Etotal": Curve1D(d["Rg_ext_Ohm"], d["Etotal_mJ"].to_numpy() * 1e-3),
        }

    def _load_energy_curve(self, name):
        d = self._csv(name)
        return {
            "Eon": Curve1D(d["IDS_A"], d["Eon_mJ"].to_numpy() * 1e-3),
            "Eoff": Curve1D(d["IDS_A"], d["Eoff_mJ"].to_numpy() * 1e-3),
        }

    def vth(self, Tj: float) -> float:
        return self.vth_curve(np.clip(Tj, self.vth_curve.xmin, self.vth_curve.xmax))

    def rds_on(self, Tj: float) -> float:
        # Only 25 C and 150 C scalar anchors are available in the requested data set.
        # Use linear interpolation as V1; replace with Fig.4/5/6 later if digitized.
        return self.RDS25 + (self.RDS150 - self.RDS25) * (Tj - 25.0) / 125.0

    @lru_cache(maxsize=32)
    def transfer_curve_at_T(self, Tj: float) -> Tuple[np.ndarray, np.ndarray]:
        temps = np.array(sorted(self.transfer_curves.keys()), dtype=float)
        T = float(np.clip(Tj, temps.min(), temps.max()))
        if T <= temps[1]:
            t0, t1 = temps[0], temps[1]
        else:
            t0, t1 = temps[1], temps[2]
        c0, c1 = self.transfer_curves[t0], self.transfer_curves[t1]
        lo = max(c0.xmin, c1.xmin)
        hi = min(c0.xmax, c1.xmax)
        vg = np.linspace(lo, hi, 500)
        i0, i1 = c0(vg), c1(vg)
        a = (T - t0) / (t1 - t0)
        ids = (1-a)*i0 + a*i1
        mask = np.isfinite(ids)
        return vg[mask], ids[mask]

    def transfer_current(self, Vgs: float, Tj: float) -> float:
        vg, ids = self.transfer_curve_at_T(Tj)
        if Vgs <= vg[0]:
            return max(0.0, float(ids[0]))
        if Vgs >= vg[-1]:
            return float(ids[-1])
        return float(PchipInterpolator(vg, ids, extrapolate=False)(Vgs))

    def transfer_gm(self, Vgs: float, Tj: float) -> float:
        vg, ids = self.transfer_curve_at_T(Tj)
        f = PchipInterpolator(vg, ids, extrapolate=False)
        x = np.clip(Vgs, vg[0], vg[-1])
        return max(0.0, float(f.derivative()(x)))

    def inverse_transfer_vgs(self, Id: float, Tj: float) -> float:
        vg, ids = self.transfer_curve_at_T(Tj)
        # Make current strictly monotonic for robust inversion.
        ids_mono = np.maximum.accumulate(ids)
        # Remove flat duplicates introduced by monotonic cleanup.
        ids_u, idx = np.unique(ids_mono, return_index=True)
        vg_u = vg[idx]
        if Id <= ids_u[0]:
            return float(vg_u[0])
        if Id >= ids_u[-1]:
            raise ValueError(f"Requested Id={Id:g} A exceeds digitized transfer curve at Tj={Tj:g} C")
        return float(PchipInterpolator(ids_u, vg_u, extrapolate=False)(Id))

    def vgs_from_q(self, q_coulomb: float) -> float:
        return self.vgs_q_curve(q_coulomb)

    def q_from_vgs(self, vgs: float) -> float:
        x = np.clip(vgs, self.q_vgs_curve.xmin, self.q_vgs_curve.xmax)
        return self.q_vgs_curve(x)

    def capacitances(self, Vds: float) -> Tuple[float, float, float]:
        # The extracted capacitance curves start reliably at ~2 V.
        v = float(np.clip(Vds, 2.0, 1195.0))
        src = self.cap17 if v <= 195.0 else self.cap18
        ciss = src["Ciss_pF"](v) * 1e-12
        coss = src["Coss_pF"](v) * 1e-12
        crss = src["Crss_pF"](v) * 1e-12
        cgd = crss
        cgs = max(ciss - crss, 1e-15)
        cds = max(coss - crss, 1e-15)
        return cgs, cgd, cds

    def eoss(self, Vds: float) -> float:
        v = np.clip(Vds, self.eoss_curve.xmin, self.eoss_curve.xmax)
        return self.eoss_curve(v)

    def cgd_integral(self, v_lo: float, v_hi: float, n=2000) -> float:
        lo, hi = sorted((max(0.0, v_lo), min(1195.0, v_hi)))
        if hi <= lo:
            return 0.0
        # Densify low-voltage region where Crss changes rapidly.
        if lo < 200:
            p1 = np.geomspace(max(lo, 2.0), min(200.0, hi), max(50, n//2))
        else:
            p1 = np.array([lo])
        p2 = np.linspace(max(200.0, lo), hi, max(50, n//2)) if hi > max(200.0, lo) else np.array([])
        v = np.unique(np.r_[p1, p2])
        cgd = np.array([self.capacitances(x)[1] for x in v])
        return float(np.trapezoid(cgd, v))

    def dynamic_qgd(self, Vdc: float, Id: float, Tj: float) -> float:
        """Scale datasheet Qgd with the extracted Crss(V) shape.

        The small-signal Crss integral alone does not reproduce the datasheet dynamic Qgd,
        so this uses the integral only as a voltage-scaling shape and anchors it to Qgd=71.5 nC
        at the datasheet reference point.
        """
        von = max(0.05, Id * self.rds_on(Tj))
        q_shape = self.cgd_integral(von, Vdc)
        ref_von = self.REF_I * self.rds_on(self.REF_T)
        q_shape_ref = self.cgd_integral(ref_von, self.REF_V)
        return self.QGD * q_shape / q_shape_ref

    def vi_energy_curve(self, Vdc: float, Id: float, which: str) -> float:
        if which not in ("Eon", "Eoff"):
            raise ValueError(which)
        if not (600.0 <= Vdc <= 800.0):
            raise ValueError("M0 VI interpolation is validated only for 600 <= Vdc <= 800 V")
        e600 = self.energy_600[which](Id)
        e800 = self.energy_800[which](Id)
        if not (np.isfinite(e600) and np.isfinite(e800)):
            raise ValueError(f"Id={Id:g} A is outside the overlapping Fig.23/Fig.24 data range")
        a = (Vdc - 600.0) / 200.0
        return float((1-a)*e600 + a*e800)

    def temp_energy_curve(self, Tj: float, which: str, commutation="body") -> float:
        key = f"{which}_{commutation}"
        if key not in self.temp_energy:
            raise ValueError(key)
        return self.temp_energy[key](Tj)

    def rg_time(self, Rg_ext: float, which: str) -> float:
        return self.rg_times[which](Rg_ext)

    def qrr(self, didt: float, Id: float = 50.0, current_exp: float = 1.0) -> float:
        # Fit Qrr ~ (di/dt)^b using the two datasheet points, then scale by Id/50.
        b = math.log(self.QRR_1/self.QRR_2) / math.log(self.DIDT_1/self.DIDT_2)
        didt_eff = max(abs(didt), 1e6)
        return self.QRR_1 * (didt_eff/self.DIDT_1)**b * (max(Id, 1e-9)/50.0)**current_exp

    def trr(self, didt: float) -> float:
        # Two-point power-law interpolation of datasheet trr vs di/dt.
        b = math.log(self.TRR_1/self.TRR_2) / math.log(self.DIDT_1/self.DIDT_2)
        return self.TRR_1 * (max(abs(didt),1e6)/self.DIDT_1)**b

    def channel_current(self, Vgs: float, Vds: float, Tj: float) -> float:
        """Smooth saturation-to-ohmic channel model using Fig.7 + Rds(on)(T)."""
        isat = max(0.0, self.transfer_current(Vgs, Tj))
        if isat <= 1e-12:
            return 0.0
        ron = max(self.rds_on(Tj), 1e-5)
        return float(isat * np.tanh(max(Vds, 0.0) / (ron*isat + 1e-12)))
