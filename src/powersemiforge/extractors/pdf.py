from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

import yaml

from .base import file_sha256
from ..schema import ExtractedParameter, ExtractionReport, Provenance


@dataclass(frozen=True)
class PDFRule:
    name: str
    pattern: str
    unit: str | None = None
    scale: float = 1.0
    multiple: bool = False
    confidence: float = 0.9
    conditions: dict[str, float | str] | None = None
    min_value: float | None = None
    max_value: float | None = None


def load_pdf_rules(path: str | Path) -> list[PDFRule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    rules = raw.get("rules", raw)
    if not isinstance(rules, list):
        raise ValueError("PDF rules file must contain a rules list")
    return [PDFRule(**rule) for rule in rules]


class PDFParameterExtractor:
    name = "pdf_text_table"
    version = "1.0"

    def __init__(self, rules: list[PDFRule], extract_tables: bool = True):
        self.rules = rules
        self.extract_tables = extract_tables

    @staticmethod
    def extract_from_pages(source: Path, pages: list[str], rules: list[PDFRule], source_hash: str) -> list[ExtractedParameter]:
        parameters: list[ExtractedParameter] = []
        completed_single_rules: set[str] = set()
        for page_number, text in enumerate(pages, start=1):
            normalized = " ".join((text or "").split())
            for rule in rules:
                if not rule.multiple and rule.name in completed_single_rules:
                    continue
                matches = list(re.finditer(rule.pattern, normalized, flags=re.IGNORECASE))
                if not rule.multiple:
                    matches = matches[:1]
                for match in matches:
                    captured = match.groupdict().get("value") or (match.group(1) if match.groups() else match.group(0))
                    value_text = captured.replace(",", "").strip()
                    try:
                        value: float | str = float(value_text) * rule.scale
                    except ValueError:
                        value = value_text
                    if isinstance(value, float):
                        if rule.min_value is not None and value < rule.min_value:
                            continue
                        if rule.max_value is not None and value > rule.max_value:
                            continue
                    parameters.append(ExtractedParameter(
                        name=rule.name, value=value, unit=rule.unit,
                        provenance=Provenance(str(source), source_hash, PDFParameterExtractor.name,
                                              PDFParameterExtractor.version, page_number, match.group(0)[:240]),
                        conditions=dict(rule.conditions or {}), confidence=rule.confidence,
                        raw_text=match.group(0)[:500],
                    ))
                    if not rule.multiple:
                        completed_single_rules.add(rule.name)
                        break
        return parameters

    def extract(self, source: str | Path) -> ExtractionReport:
        source = Path(source).resolve()
        source_hash = file_sha256(source)
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires: pip install 'powersemiforge[pdf]'") from exc
        pages: list[str] = []
        tables: list[dict[str, Any]] = []
        warnings: list[str] = []
        with pdfplumber.open(source) as document:
            metadata = dict(document.metadata or {})
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text() or ""
                pages.append(text)
                if not text:
                    warnings.append(f"page {page_number}: no extractable text")
                if self.extract_tables:
                    for table_index, table in enumerate(page.extract_tables() or []):
                        tables.append({"page": page_number, "index": table_index, "rows": table})
        parameters = self.extract_from_pages(source, pages, self.rules, source_hash)
        return ExtractionReport(
            schema_version="1.0", status="COMPLETE" if parameters else "COMPLETE_NO_MATCHES",
            source_file=str(source), source_sha256=source_hash, extractor=f"{self.name}:{self.version}",
            parameters=parameters, tables=tables,
            metadata={"page_count": len(pages), "pdf_metadata": metadata, "rule_count": len(self.rules)},
            warnings=warnings,
        )
