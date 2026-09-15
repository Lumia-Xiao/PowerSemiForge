from __future__ import annotations
from dataclasses import dataclass, asdict
from .device_data import C2M0025120DData, OperatingPoint


@dataclass
class M0Result:
    Eon_J: float
    Eoff_J: float
    Esw_J: float
    Psw_W: float
    K_vi_on: float
    K_vi_off: float
    K_t_on: float
    K_t_off: float
    K_rg_on: float
    K_rg_off: float
    note: str

    def as_dict(self): return asdict(self)


class M0LossSurface:
    """Anchored datasheet loss-surface model.

    Absolute anchor: electrical-characteristics table at 800 V / 50 A / 2.5 ohm / 25 C.
    Shapes: Fig.23/24 (V,I), Fig.26 (T), and Fig.27 switching times as a robust Rg shape.
    Fig.25 is intentionally not used because the extracted Etotal != Eon + Eoff.
    """
    def __init__(self, data: C2M0025120DData):
        self.d = data
        self._vi_ref_on = self.d.vi_energy_curve(800.0, 50.0, "Eon")
        self._vi_ref_off = self.d.vi_energy_curve(800.0, 50.0, "Eoff")
        self._t_ref_on = self.d.temp_energy_curve(25.0, "Eon", "body")
        self._t_ref_off = self.d.temp_energy_curve(25.0, "Eoff", "body")
        self._tr_ref = self.d.rg_time(2.5, "tr")
        self._tf_ref = self.d.rg_time(2.5, "tf")

    def predict(self, op: OperatingPoint) -> M0Result:
        vi_on = self.d.vi_energy_curve(op.Vdc, op.Id, "Eon")
        vi_off = self.d.vi_energy_curve(op.Vdc, op.Id, "Eoff")
        k_vi_on = vi_on / self._vi_ref_on
        k_vi_off = vi_off / self._vi_ref_off

        k_t_on = self.d.temp_energy_curve(op.Tj, "Eon", "body") / self._t_ref_on
        k_t_off = self.d.temp_energy_curve(op.Tj, "Eoff", "body") / self._t_ref_off

        k_rg_on = self.d.rg_time(op.Rg_ext_on, "tr") / self._tr_ref
        k_rg_off = self.d.rg_time(op.Rg_off, "tf") / self._tf_ref

        eon = self.d.REF_EON * k_vi_on * k_t_on * k_rg_on
        eoff = self.d.REF_EOFF * k_vi_off * k_t_off * k_rg_off
        return M0Result(
            Eon_J=eon, Eoff_J=eoff, Esw_J=eon+eoff, Psw_W=(eon+eoff)*op.fsw,
            K_vi_on=k_vi_on, K_vi_off=k_vi_off,
            K_t_on=k_t_on, K_t_off=k_t_off,
            K_rg_on=k_rg_on, K_rg_off=k_rg_off,
            note="Single-point anchored datasheet surface; valid mainly inside digitized curve domain."
        )
