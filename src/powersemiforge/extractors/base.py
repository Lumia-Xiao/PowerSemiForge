from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Protocol

from ..schema import ExtractionReport


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Extractor(Protocol):
    name: str
    version: str

    def extract(self, source: str | Path) -> ExtractionReport: ...

