# MOSFET data fleet onboarding

This document defines how the external PDF corpus is converted into PowerSemiForge devices and switching-loss results. It complements the mandatory repository instructions in `AGENTS.md`.

## Corpus snapshot

The planning snapshot taken on 2026-09-15 found 1,065 PDFs:

| Vendor | PDFs |
|---|---:|
| Wolfspeed | 629 |
| Rohm | 219 |
| Infineon | 177 |
| Navitas | 24 |
| Mitsubishi | 16 |

There are 178 duplicate-filename groups, but filename equality is not proof of byte equality. The first execution phase must regenerate counts and SHA-256 groups; this table is context, not an acceptance record.

The corpus includes more than discrete MOSFET datasheets. It contains diode, module, converter, Si, SiC, and GaN material. All PDFs can be inventoried and extracted, but only applicable and sufficiently evidenced devices can enter a switching-loss model.

## Local source configuration

Keep the external data tree outside Git and expose it to commands without hard-coding a workstation path:

```powershell
$env:PSFORGE_DATA_ROOT = '<path-to-MOSFET_Data>'
Test-Path -LiteralPath $env:PSFORGE_DATA_ROOT
```

All committed catalogs use paths relative to this root. Extraction artifacts go under `workspace/` or `artifacts/`, both of which are ignored by Git.

## Phase gates

### Gate 0: scalable platform readiness

Before fleet extraction, implement and test:

- a versioned source-inventory schema and deterministic inventory command;
- SHA-256 exact-duplicate grouping;
- document classification and candidate part-number fields;
- rule-pack routing by vendor, technology, and revision family;
- resumable extraction with one terminal record per input PDF;
- a machine-readable progress ledger;
- manifest-driven device discovery instead of the current C2M0025120D-only registry.

The current regex rules are a C2M0025120D example, not a fleet rule pack.

### Gate 1: complete inventory

Create one row per PDF with at least:

| Field | Meaning |
|---|---|
| `source_id` | stable ID derived from SHA-256 |
| `source_sha256` | full file digest |
| `relative_path` | path relative to the configured data root |
| `vendor` | normalized vendor |
| `source_filename` | original filename |
| `size_bytes` | source size |
| `document_type` | datasheet, application note, module, diode, converter, unknown, etc. |
| `technology` | Si, SiC, GaN, diode, module, unknown |
| `candidate_part_number` | extracted candidate, never silently assumed from filename |
| `duplicate_of` | canonical source ID for byte-identical documents |
| `state` | lifecycle or blocker state |
| `error` | explicit failure reason |

Acceptance requires the inventory row count to equal the discovered PDF count and every SHA-256 operation to have a recorded outcome.

### Gate 2: extract every unique PDF

Work in this order: Infineon, Mitsubishi, Navitas, Rohm, Wolfspeed. For each vendor:

1. classify layout/revision families;
2. select representative golden PDFs;
3. build versioned rule packs and expected-value tests;
4. run a small pilot and review every result;
5. run the full vendor batch incrementally;
6. record complete, no-match, excluded, and failed counts;
7. resolve or explicitly block all critical QA findings.

Required normalized parameter groups include identity, technology, package, absolute ratings, gate-drive conditions, static conduction parameters, switching-energy anchors, switching times, gate charge, capacitances, output-capacitance energy, reverse recovery, thermal parameters, and every available curve with its test conditions.

Extraction is not registration. Keep raw extraction reports immutable; create normalized records as separate reviewed artifacts.

Gate 2 closes only after every unique PDF has a terminal extraction state and the fleet summary reconciles to the inventory. Per the project sequence, no fleet device registration starts before this gate closes.

### Gate 3: register eligible devices

Group reviewed source revisions by verified part number. Then:

1. create `vendor/part_number/` with `psforge device scaffold`;
2. build and validate the canonical `DeviceRecord`;
3. populate the manifest using traceable extracted values only;
4. link source hashes and revisions;
5. declare supported domains and missing evidence;
6. add manifest/schema/registry tests;
7. assign `REGISTERED`, `BLOCKED_*`, or `NOT_APPLICABLE`.

Exact duplicate PDFs do not create duplicate devices. Product-family documents may create multiple device records only when each part's values and conditions can be separated reliably.

### Gate 4: determine model readiness

Assess each registered device against a model evidence matrix:

| Model | Minimum evidence |
|---|---|
| M0 | conditioned Eon/Eoff reference plus the voltage, current, temperature, and gate-resistance dimensions used by that model's interpolation contract |
| M1 | M0 anchors where applicable; transfer characteristic; threshold/gate-charge data; Qgd or Cgd(V); Eoss or equivalent; reverse-recovery data for the commutation path |
| M2 | M1 evidence plus reviewed Lg/Ls/Lloop sensitivity formulation and stress equations for the technology/package class |
| M3 | M1/M2 evidence plus a reviewed transient stage model, numerical convergence criteria, and calibration/holdout transient or energy evidence |

Missing evidence produces a blocker; it does not authorize a guessed value. A device can be M0-ready while M1-M3 remain blocked. A diode can be registered while MOSFET switching models remain `NOT_APPLICABLE`.

### Gate 5: implement, calibrate, and validate

- Implement shared technology adapters first, followed by device data/configuration.
- Keep physical equations separate from device assets.
- Create immutable calibration YAML with reference parasitics and source provenance.
- Freeze independent holdout points before fitting.
- Add reference-anchor, monotonic-trend, out-of-domain, changed-parasitics, solver-state, convergence, and holdout tests.
- Report MAE, RMSE, MAPE where meaningful, per-condition errors, uncertainty basis, and evidence limitations.

Only a model that passes these checks may set the device to `VALIDATED` and `BATCH_READY`.

### Gate 6: fleet calculations and reports

Run deterministic matrices only for `BATCH_READY` device/model pairs. Results must retain device ID, model ID, calibration ID, source/manifest version, operating point, parasitics, solver status, run ID, and timing. Failures remain in the denominator and appear in machine-readable reports.

## Review and commit strategy

Use one logical commit per reviewed work unit, for example:

1. inventory/schema/tooling;
2. one vendor rule pack plus golden tests;
3. one vendor extraction summary;
4. a reviewable device-registration batch;
5. one technology adapter or model family;
6. calibration/validation evidence;
7. fleet result/report generation.

Do not publish bulk extracted manufacturer data until `docs/DATA_GOVERNANCE.md` has been applied and redistribution rights are explicit.
