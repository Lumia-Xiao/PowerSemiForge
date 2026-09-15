from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import available_devices, calculate
from .exporting import export_json, export_summary_csv, export_waveform_csvs
from .plotting import plot_waveforms
from .schemas import CalculationRequest, OperatingPointInput, ParasiticsInput


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="switching-loss", description="Datasheet-driven switching-loss calculator")
    parser.add_argument("--version", action="version", version="switching-loss-engine 0.6.0")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-devices", help="list registered device ids")
    estimate = commands.add_parser("estimate", help="calculate one operating point")
    estimate.add_argument("--device", default="C2M0025120D")
    estimate.add_argument("--model", choices=["M0", "M1", "M2", "M3"], default="M3")
    estimate.add_argument("--calibration", help="explicit calibration profile id")
    estimate.add_argument("--vdc", type=float, required=True)
    estimate.add_argument("--id", dest="current", type=float, required=True)
    estimate.add_argument("--tj", type=float, default=25.0)
    estimate.add_argument("--rg-on", type=float, default=2.5)
    estimate.add_argument("--rg-off", type=float, default=2.5)
    estimate.add_argument("--vg-on", type=float, default=20.0)
    estimate.add_argument("--vg-off", type=float, default=-5.0)
    estimate.add_argument("--fsw", type=float, default=100e3)
    estimate.add_argument("--r-driver-on", type=float, default=0.5)
    estimate.add_argument("--r-driver-off", type=float, default=0.5)
    estimate.add_argument("--lg-nh", type=float, default=5.0)
    estimate.add_argument("--ls-nh", type=float, default=5.0)
    estimate.add_argument("--lloop-nh", type=float, default=20.0)
    estimate.add_argument("--rloop", type=float, default=0.05)
    estimate.add_argument("--loop-loss-fraction", type=float, default=0.25)
    estimate.add_argument("--dt-ns", type=float, default=0.1)
    estimate.add_argument("--no-convergence-check", action="store_true")
    estimate.add_argument("--json", type=Path)
    estimate.add_argument("--csv", type=Path)
    estimate.add_argument("--waveform-dir", type=Path)
    estimate.add_argument("--plot", type=Path)
    validate = commands.add_parser("validate", help="evaluate the versioned datasheet/XML holdout")
    validate.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list-devices":
        print("\n".join(available_devices()))
        return 0
    if args.command == "validate":
        from .validation import run_default_validation
        report = run_default_validation()
        text = json.dumps(report, indent=2, ensure_ascii=False)
        print(text)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        return 0
    need_waveforms = bool(args.waveform_dir or args.plot)
    request = CalculationRequest(
        device_id=args.device, model=args.model,
        operating_point=OperatingPointInput(args.vdc, args.current, args.tj, args.rg_on, args.rg_off,
                                            args.vg_on, args.vg_off, args.fsw),
        parasitics=ParasiticsInput(args.r_driver_on, args.r_driver_off, args.lg_nh * 1e-9,
                                  args.ls_nh * 1e-9, args.lloop_nh * 1e-9, args.rloop, args.loop_loss_fraction),
        calibration_id=args.calibration,
        return_waveforms=need_waveforms, time_step_s=args.dt_ns * 1e-9,
        convergence_check=not args.no_convergence_check,
    )
    result = calculate(request)
    print(json.dumps(result.as_dict(include_waveforms=False), indent=2, ensure_ascii=False))
    if args.json:
        export_json(result, args.json)
    if args.csv:
        export_summary_csv(result, args.csv)
    if args.waveform_dir:
        export_waveform_csvs(result, args.waveform_dir)
    if args.plot:
        plot_waveforms(result, args.plot)
    return 0 if result.solver.converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
