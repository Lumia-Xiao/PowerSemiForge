# PowerSemiForge

**PowerSemiForge (PSForge)** is an open, provenance-first pipeline for turning power-semiconductor datasheets and manufacturer model files into reproducible device records, calculation models, simulation matrices, processed results, and publication-ready plots.

The repository includes Wolfspeed C2M0025120D as the first end-to-end reference device. Its M0-M3 switching-loss models remain available through the compatibility package `switching_loss_engine`.

> Status: research alpha. The software is suitable for reproducible engineering studies, but model outputs must be checked against independent measurements before safety-critical use.

## Pipeline

```mermaid
flowchart LR
  A["PDF / XML / CSV sources"] --> B["Extraction plugins"]
  B --> C["Canonical device record"]
  C --> D["Versioned device library"]
  D --> E["Model plugins and calibration profiles"]
  E --> F["Batch simulation matrix"]
  F --> G["Results, QA metrics, and plots"]
```

## What is implemented

- Incremental batch PDF extraction with regex rules, table capture, SHA-256 provenance, per-file errors, and worker control.
- PLECS XML extraction for gate-resistance variables and turn-on/turn-off loss tables.
- Canonical, versioned device-record schema with source/page/locator/confidence metadata.
- Device scaffolding for a consistent multi-vendor library layout.
- Deterministic operating-point matrix expansion and batch M0-M3 execution.
- CSV result aggregation and energy-versus-current visualization.
- C2M0025120D M0-M3 implementation, fixed calibration profiles, solver-state reporting, waveform export, and holdout validation.
- Backward-compatible `switching-loss` CLI plus the public `psforge` CLI.

## Installation

```bash
python -m venv .venv
python -m pip install -e ".[pdf]"
```

PDF support is optional so calculation-only deployments can install the smaller base package with `pip install -e .`.

## Quick start

List calculation-ready devices:

```bash
psforge device list
```

Extract a directory of PDFs incrementally:

```bash
psforge extract pdf \
  --input workspace/pdfs \
  --rules examples/pdf_rules_c2m.yaml \
  --output artifacts/extracted/pdf \
  --workers 4
```

Extract manufacturer PLECS XML files:

```bash
psforge extract xml \
  --input workspace/xml \
  --output artifacts/extracted/xml \
  --workers 4
```

Create a new device workspace:

```bash
psforge device scaffold \
  --library workspace/device_library \
  --vendor Infineon \
  --part IMZ120R030M1H
```

Generate a model implementation and regression-test scaffold:

```bash
psforge model scaffold --device-dir workspace/device_library/infineon/IMZ120R030M1H --model-id M0
```

Audit an extraction report before promoting values into a device record:

```bash
psforge quality extraction --input artifacts/extracted/pdf/device-report.json
```

Run and visualize a simulation matrix:

```bash
psforge simulate --matrix examples/batch_matrix.yaml --output artifacts/runs/c2m-demo
psforge report --input artifacts/runs/c2m-demo/results.csv --output artifacts/reports/c2m-demo
```

Calculate one operating point:

```bash
psforge loss --device C2M0025120D --model M3 --vdc 800 --id 40 --tj 125 --rg-on 5 --rg-off 5
```

## Repository layout

```text
src/powersemiforge/             public pipeline, schemas, extraction and batch tools
src/switching_loss_engine/      validated C2M0025120D calculation compatibility core
src/powersemiforge/device_library/
                                distributable manifests, extracted curves and profiles
examples/                       extraction rules and simulation matrices
tests/                          unit, regression, validation and pipeline tests
docs/                           architecture, data policy and contributor guides
```

## Reproducibility rules

1. Every source file is identified by SHA-256.
2. Every extracted value retains its source, page or locator, units, conditions, extractor version, and confidence.
3. Calibration profiles are immutable YAML artifacts; models never refit themselves during prediction.
4. Calibration and holdout points are explicitly separated.
5. A batch run receives a deterministic ID from its canonical matrix configuration.
6. Failures are recorded per source or operating point rather than silently dropped.

## Data and licensing

Raw manufacturer PDFs and model files are ignored by Git by default. Before publishing extracted manufacturer data, verify that redistribution is permitted. See [Data governance](docs/DATA_GOVERNANCE.md).

## Documentation

- [Chinese introduction](docs/README_zh.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Adding a device](docs/ADDING_A_DEVICE.md)
- [Data governance](docs/DATA_GOVERNANCE.md)
- [C2M0025120D dataset card](docs/C2M0025120D_DATASET.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## License

The source code is released under the MIT License. Manufacturer documents, model files, trademarks, and extracted datasets may be governed by separate terms.
