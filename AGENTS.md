# PowerSemiForge agent instructions

This file applies to the entire repository. It is the execution contract for Codex and other coding agents working on the MOSFET data onboarding program.

## Mission and current boundary

PowerSemiForge converts manufacturer documents into traceable device records and, only when the required evidence exists, validated switching-loss models. The current calculation-ready reference is Wolfspeed C2M0025120D. Do not describe the repository as fleet-ready until the active onboarding plan has passed every gate.

The required fleet sequence is strict:

1. inventory and extract all in-scope PDFs;
2. finish extraction QA and record unresolved documents;
3. register eligible devices;
4. assess model readiness, implement models, calibrate, and validate;
5. run fleet switching-loss calculations and reporting.

Do not register devices before the extraction gate for the full corpus is closed. Do not calculate loss for a device merely because it has been registered.

## Required startup procedure

Before changing files:

1. Read this file completely.
2. Read `README.md`, `Plan/README.md`, `docs/ARCHITECTURE.md`, `docs/FLEET_ONBOARDING.md`, `docs/ADDING_A_DEVICE.md`, and `docs/DATA_GOVERNANCE.md`.
3. Count Markdown files in `Plan/Active/`.
   - More than one: stop and report the plan-lock violation.
   - Exactly one: work only on the next unchecked item in that plan unless the user explicitly changes scope.
   - Zero: create one Active plan for material multi-step work before implementation.
4. Inspect `git status --short --branch`. Preserve unrelated user changes.
5. State the current phase, target batch, expected outputs, and acceptance gate before running a write operation.

Update the existing Active plan instead of creating side plans. When the entire plan is complete, mark it `COMPLETED`, move it to `Plan/Completed/`, and leave `Plan/Active/` with only `.gitkeep`.

## Source-data safety

- Treat the external `MOSFET_Data` tree as read-only source evidence.
- Never rename, move, delete, overwrite, compress, or reorganize source PDFs.
- Never run recursive cleanup against the source tree.
- Use a user-supplied CLI path or the `PSFORGE_DATA_ROOT` environment variable. Never commit a user-specific absolute path.
- Write intermediate extraction output only under ignored `workspace/` or `artifacts/` directories.
- Identify every source by SHA-256 and use paths relative to the configured data root in versioned catalogs.
- Exact duplicates must be represented by one canonical source plus duplicate references; never silently discard them.
- Do not commit raw PDFs, manufacturer XML/SPICE models, credentials, virtual environments, caches, or generated bulk output.
- Before any bulk mutation or deletion, show the exact resolved targets and obtain explicit user approval.

## Evidence and lifecycle states

Every document and device must have an explicit state. Use only these forward states:

`INVENTORIED -> EXTRACTED -> QA_REVIEWED -> REGISTERED -> MODEL_READY -> VALIDATED -> BATCH_READY`

Use `BLOCKED_*`, `EXTRACTION_FAILED`, `NOT_A_DEVICE_DATASHEET`, `DUPLICATE_SOURCE`, or `NOT_APPLICABLE` when appropriate. Never advance a record to make progress statistics look better.

- `EXTRACTED` means a machine-readable report exists even if it contains no matches.
- `QA_REVIEWED` means units, conditions, pages/locators, duplicate values, and confidence were reviewed.
- `REGISTERED` means a valid device record and manifest exist with provenance and an explicit supported domain.
- `MODEL_READY` means one named model has all required inputs and an immutable calibration profile.
- `VALIDATED` means calibration and holdout evidence are separate and regression thresholds pass.
- `BATCH_READY` means the unified API and batch runner can execute the device without a device-specific manual step.

Registration is not evidence that M0-M3 are all applicable. Diodes, modules, Si MOSFETs, SiC MOSFETs, and GaN devices require different records and may require different model families.

## Batch execution rules

- Maintain a complete inventory ledger before extraction. Required fields are defined in `docs/FLEET_ONBOARDING.md`.
- Develop and test rule packs by vendor, technology, and document revision family.
- For each rule pack, manually verify representative golden PDFs before a pilot batch.
- Run a small resumable pilot before the full vendor batch. Every input must produce a success, no-match, duplicate, excluded, or failure record.
- Never hide failed files or reduce the denominator when reporting coverage.
- Preserve extracted raw text/table evidence separately from normalized device records.
- Normalize values to canonical SI units, while retaining original value, unit, condition, page, locator, extractor version, and source hash.
- Resolve ambiguous part numbers, table headings, test conditions, and min/typ/max columns before promotion.
- Process commits in reviewable batches. Do not mix extraction-engine changes, thousands of generated records, model physics, and reports in one commit.

## Registration and architecture rules

- Use short normalized paths: `vendor/part_number/`; do not reproduce deep source-tree paths in the device library.
- A source revision maps to the same canonical device only after identity and revision checks.
- Replace the current hard-coded calculation registry with manifest-driven discovery before fleet registration.
- Reuse technology/model-family adapters. Do not copy the C2M0025120D Python implementation into every device directory.
- Keep source extraction, normalized records, model code, calibration, holdout data, and generated results as separate artifacts.
- A device manifest must declare technology, ratings, source hashes, available curves, calibration IDs, supported domain, lifecycle state, and known limitations.
- Public redistribution of extracted curves requires an explicit data-rights decision; otherwise commit only code, schemas, hashes, and citations.

## Model and calibration rules

- Never invent a missing parameter, curve, test condition, or unit.
- Never infer circuit parasitics from a device datasheet unless an explicit package/model source provides them. Gate-loop and power-loop parasitics remain calculation inputs.
- M0 is allowed only when its reference energies and required interpolation dimensions are supported by extracted evidence.
- M1 requires traceable transfer, threshold/gate-charge, capacitance or Miller-charge, output-capacitance-energy, and reverse-recovery evidence appropriate to the device technology.
- M2 and M3 require the M1 evidence plus a defensible parasitic formulation and model-family validation.
- GaN, Si MOSFET, SiC MOSFET, discrete, module, and diode behavior must not be forced through one model without an explicit reviewed adapter.
- Calibration profiles are immutable, versioned YAML files loaded explicitly. Prediction code must never fit or rewrite calibration.
- Freeze calibration and holdout sets before error reporting. A source point cannot appear in both.
- Report interpolation and extrapolation domains. Out-of-domain results must emit a warning or fail according to the model contract.
- Do not mark a model validated from datasheet-anchor reproduction alone. Record the evidence limitation when independent DPT measurements are unavailable.

## Quality gates and verification

For code changes, run at minimum:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m powersemiforge device list
```

Also run the smallest relevant extraction, registration, model, batch, and report smoke tests. Check `git diff --check`, inspect every staged path, and confirm `Plan/Active` contains at most one Markdown file.

A phase is complete only when its deliverables exist, machine-readable counts reconcile, failures are listed, tests pass, and the Active plan records the evidence. Report exact counts for total, unique, duplicate, succeeded, no-match, excluded, failed, registered, model-ready, and validated items.

Do not commit or push unless the user requests it. Never claim remote success without reading back the remote commit and CI status.
