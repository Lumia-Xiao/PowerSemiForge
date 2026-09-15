from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

from .extractors import PDFParameterExtractor, PlecsXMLExtractor, file_sha256, load_pdf_rules


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return slug or "unnamed"


@dataclass(frozen=True)
class IngestResult:
    source: str
    output: str | None
    status: str
    source_sha256: str | None = None
    error: str | None = None


class BatchIngestor:
    """Incremental, deterministic batch extraction with one JSON artifact per source."""

    def __init__(self, output_dir: str | Path, workers: int = 1):
        self.output_dir = Path(output_dir)
        self.workers = max(1, int(workers))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.output_dir / "extraction-index.json"
        self.index = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"schema_version": "1.0", "sources": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _run_one(self, path: Path, extractor, force: bool) -> IngestResult:
        digest = file_sha256(path)
        output = self.output_dir / f"{safe_slug(path.stem)}-{digest[:12]}.json"
        previous = self.index["sources"].get(str(path.resolve()))
        if not force and previous and previous.get("sha256") == digest and output.exists():
            return IngestResult(str(path), str(output), "SKIPPED_UNCHANGED", digest)
        try:
            report = extractor.extract(path)
            report.save(output)
            return IngestResult(str(path), str(output), report.status, digest)
        except Exception as exc:  # batch jobs must record per-file failures
            return IngestResult(str(path), None, "FAILED", digest, f"{type(exc).__name__}: {exc}")

    def run(self, sources: list[Path], extractor, force: bool = False) -> list[IngestResult]:
        ordered = sorted({path.resolve() for path in sources})
        results: list[IngestResult] = []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._run_one, path, extractor, force): path for path in ordered}
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item.source)
        for result in results:
            if result.source_sha256:
                self.index["sources"][result.source] = {
                    "sha256": result.source_sha256, "status": result.status, "output": result.output,
                    "error": result.error,
                }
        self.index_path.write_text(json.dumps(self.index, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.output_dir / "last-run.json").write_text(
            json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return results


def discover_sources(path: str | Path, suffix: str, recursive: bool = True) -> list[Path]:
    path = Path(path)
    if path.is_file():
        return [path]
    pattern = f"**/*{suffix}" if recursive else f"*{suffix}"
    return [candidate for candidate in path.glob(pattern) if candidate.is_file()]


def ingest_pdfs(input_path: str | Path, rules_path: str | Path, output_dir: str | Path,
                 workers: int = 1, force: bool = False) -> list[IngestResult]:
    extractor = PDFParameterExtractor(load_pdf_rules(rules_path))
    return BatchIngestor(output_dir, workers).run(discover_sources(input_path, ".pdf"), extractor, force)


def ingest_xml(input_path: str | Path, output_dir: str | Path,
               workers: int = 1, force: bool = False) -> list[IngestResult]:
    return BatchIngestor(output_dir, workers).run(discover_sources(input_path, ".xml"), PlecsXMLExtractor(), force)

