from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


def audit_extraction(report_path: str | Path, low_confidence_threshold: float = 0.8) -> dict:
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    parameters = report.get("parameters", [])
    counts = Counter(item.get("name") for item in parameters)
    duplicates = sorted(name for name, count in counts.items() if name and count > 1)
    missing_units = sorted({item.get("name") for item in parameters if item.get("unit") in (None, "")})
    low_confidence = sorted({item.get("name") for item in parameters if float(item.get("confidence", 0)) < low_confidence_threshold})
    missing_provenance = sorted({
        item.get("name") for item in parameters
        if not item.get("provenance", {}).get("source_sha256") or not item.get("provenance", {}).get("extractor")
    })
    blockers = bool(report.get("errors") or missing_provenance)
    warnings = bool(duplicates or missing_units or low_confidence or report.get("warnings"))
    return {
        "schema_version": "1.0", "source_report": str(report_path.resolve()),
        "status": "FAIL" if blockers else ("REVIEW" if warnings else "PASS"),
        "parameter_count": len(parameters), "table_count": len(report.get("tables", [])),
        "duplicates": duplicates, "missing_units": missing_units,
        "low_confidence": low_confidence, "missing_provenance": missing_provenance,
        "extractor_warnings": report.get("warnings", []), "extractor_errors": report.get("errors", []),
    }

