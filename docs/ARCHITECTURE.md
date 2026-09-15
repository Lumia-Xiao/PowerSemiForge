# Architecture

PowerSemiForge separates evidence, device records, models, execution, and reports so that scaling the device count does not duplicate orchestration code.

## Layers

1. **Source layer** - immutable PDF/XML/CSV files outside Git or in an approved data store.
2. **Extraction layer** - format-specific plugins return a common `ExtractionReport`.
3. **Record layer** - normalized parameters and assets conform to `device-record.schema.json`.
4. **Device library** - one short vendor/part path containing manifest, curves, calibrations, and validation datasets.
5. **Model layer** - device-agnostic interfaces plus device adapters. A model receives all circuit parasitics explicitly.
6. **Execution layer** - deterministic matrix expansion, per-job failure capture, and machine-readable run manifests.
7. **Reporting layer** - summaries and plots generated only from immutable result tables.

## Extension contracts

- Extractors implement `extract(source) -> ExtractionReport`.
- Device records preserve provenance for every parameter.
- Calculation-ready devices register a `DeviceDefinition` factory.
- Calibration YAMLs declare device, model, reference point, reference parasitics, and evidence source.
- Batch outputs always include `run_id`, `job_index`, inputs, calibration ID, solver state, timing, and energies.

## Scale strategy

- File-level SHA-256 enables incremental extraction.
- One JSON artifact per source avoids a single global write lock.
- Batch failures are isolated and retained.
- Short normalized vendor/part paths avoid Windows path-length problems.
- Raw data, generated artifacts, environments, and caches remain outside version control.

