from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from switching_loss_engine import CalculationRequest, OperatingPointInput, ParasiticsInput, available_devices, calculate

from . import __version__
from .batch import run_batch
from .pipeline import ingest_pdfs, ingest_xml
from .reporting import build_report
from .scaffold import scaffold_device
from .modeling import scaffold_model
from .quality import audit_extraction


def _json(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="psforge", description="PowerSemiForge datasheet-to-simulation pipeline")
    parser.add_argument("--version", action="version", version=f"PowerSemiForge {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    device = commands.add_parser("device", help="device catalog operations")
    device_commands = device.add_subparsers(dest="device_command", required=True)
    device_commands.add_parser("list", help="list calculation-ready devices")
    scaffold = device_commands.add_parser("scaffold", help="create a new device workspace")
    scaffold.add_argument("--library", type=Path, default=Path("device_library"))
    scaffold.add_argument("--vendor", required=True)
    scaffold.add_argument("--part", required=True)
    scaffold.add_argument("--technology", default="SiC MOSFET")

    model = commands.add_parser("model", help="model plugin operations")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_scaffold = model_commands.add_parser("scaffold", help="create a traceable model and test scaffold")
    model_scaffold.add_argument("--device-dir", type=Path, required=True)
    model_scaffold.add_argument("--model-id", default="M0")

    extract = commands.add_parser("extract", help="batch source extraction")
    extract_commands = extract.add_subparsers(dest="extract_command", required=True)
    pdf = extract_commands.add_parser("pdf", help="extract parameters and tables from PDFs")
    pdf.add_argument("--input", type=Path, required=True)
    pdf.add_argument("--rules", type=Path, required=True)
    pdf.add_argument("--output", type=Path, required=True)
    pdf.add_argument("--workers", type=int, default=1)
    pdf.add_argument("--force", action="store_true")
    xml = extract_commands.add_parser("xml", help="extract PLECS XML tables")
    xml.add_argument("--input", type=Path, required=True)
    xml.add_argument("--output", type=Path, required=True)
    xml.add_argument("--workers", type=int, default=1)
    xml.add_argument("--force", action="store_true")

    simulate = commands.add_parser("simulate", help="run a simulation matrix")
    simulate.add_argument("--matrix", type=Path, required=True)
    simulate.add_argument("--output", type=Path, required=True)

    report = commands.add_parser("report", help="summarize and visualize batch results")
    report.add_argument("--input", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)

    quality = commands.add_parser("quality", help="quality gates for extracted artifacts")
    quality_commands = quality.add_subparsers(dest="quality_command", required=True)
    extraction_quality = quality_commands.add_parser("extraction", help="audit one extraction report")
    extraction_quality.add_argument("--input", type=Path, required=True)
    extraction_quality.add_argument("--low-confidence", type=float, default=0.8)

    loss = commands.add_parser("loss", help="calculate one switching operating point")
    loss.add_argument("--device", default="C2M0025120D")
    loss.add_argument("--model", choices=["M0", "M1", "M2", "M3"], default="M3")
    loss.add_argument("--vdc", type=float, required=True)
    loss.add_argument("--id", dest="current", type=float, required=True)
    loss.add_argument("--tj", type=float, default=25.0)
    loss.add_argument("--rg-on", type=float, default=2.5)
    loss.add_argument("--rg-off", type=float, default=2.5)
    loss.add_argument("--calibration")
    loss.add_argument("--fast", action="store_true", help="skip half-step convergence check")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "device":
        if args.device_command == "list":
            _json({"devices": available_devices()})
        else:
            path = scaffold_device(args.library, args.vendor, args.part, args.technology)
            _json({"status": "CREATED", "path": str(path.resolve())})
        return 0
    if args.command == "model":
        paths = scaffold_model(args.device_dir, args.model_id)
        _json({"status": "CREATED", "files": {key: str(value.resolve()) for key, value in paths.items()}})
        return 0
    if args.command == "extract":
        if args.extract_command == "pdf":
            results = ingest_pdfs(args.input, args.rules, args.output, args.workers, args.force)
        else:
            results = ingest_xml(args.input, args.output, args.workers, args.force)
        _json([asdict(result) for result in results])
        return 1 if any(result.status == "FAILED" for result in results) else 0
    if args.command == "simulate":
        manifest = run_batch(args.matrix, args.output)
        _json(manifest)
        return 1 if manifest["failed"] else 0
    if args.command == "report":
        _json(build_report(args.input, args.output))
        return 0
    if args.command == "quality":
        audit = audit_extraction(args.input, args.low_confidence)
        _json(audit)
        return 1 if audit["status"] == "FAIL" else 0
    result = calculate(CalculationRequest(
        args.device, args.model,
        OperatingPointInput(args.vdc, args.current, args.tj, args.rg_on, args.rg_off),
        ParasiticsInput(), calibration_id=args.calibration, convergence_check=not args.fast,
    ))
    _json(result.as_dict(include_waveforms=False))
    return 0 if result.solver.converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
