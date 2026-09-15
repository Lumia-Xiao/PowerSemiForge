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

## Switching-loss calculation models

The calculation core currently implements M0-M3 for Wolfspeed C2M0025120D. All four models return turn-on energy `Eon`, turn-off energy `Eoff`, total switching energy, and switching power:

$$
E_{sw}=E_{on}+E_{off}, \qquad P_{sw}=f_{sw}E_{sw}.
$$

`Psw` therefore assumes one turn-on and one turn-off event per switching period for the modeled device. The models are different fidelity levels, not four interchangeable implementations of the same equations.

### Inputs and units

The public API uses [`CalculationRequest`](src/switching_loss_engine/schemas.py). Its main inputs are:

| Input | Symbol | Unit | Default | Accepted range or meaning |
|---|---:|---:|---:|---|
| `vdc_V` | $V_{dc}$ | V | required | $0 < V_{dc} \le 1200$ |
| `id_A` | $I_D$ | A | required | $0 < I_D \le 120$ |
| `tj_C` | $T_j$ | °C | 25 | $-55 \le T_j \le 150$ |
| `rg_on_ohm` | $R_{g,on}^{ext}$ | Ω | 2.5 | external turn-on gate resistance, non-negative |
| `rg_off_ohm` | $R_{g,off}^{ext}$ | Ω | 2.5 | external turn-off gate resistance, non-negative |
| `vg_on_V` | $V_{g,on}$ | V | 20 | positive gate-drive rail |
| `vg_off_V` | $V_{g,off}$ | V | -5 | negative/off gate-drive rail |
| `fsw_Hz` | $f_{sw}$ | Hz | 100,000 | used only to convert energy to switching power |
| `r_driver_on_ohm` | $R_{drv,on}$ | Ω | 0.5 | driver/source-path turn-on resistance |
| `r_driver_off_ohm` | $R_{drv,off}$ | Ω | 0.5 | driver/sink-path turn-off resistance |
| `lg_H` | $L_g$ | H | 5 nH | gate-loop inductance |
| `ls_H` | $L_s$ | H | 5 nH | common-source inductance |
| `lloop_H` | $L_{loop}$ | H | 20 nH | commutation/power-loop inductance |
| `rloop_ohm` | $R_{loop}$ | Ω | 0.05 | commutation-loop series resistance |
| `loop_loss_fraction` | $\eta_{loop}$ | 1 | 0.25 | fraction of loop magnetic energy assigned to semiconductor loss, from 0 to 1 |
| `time_step_s` | $\Delta t$ | s | 0.1 ns | M3 only; accepted range 0.01-2 ns |

The total gate-path resistances used by M1-M3 are

$$
R_{g,on}=R_{g,int}+R_{g,on}^{ext}+R_{drv,on}, \qquad
R_{g,off}=R_{g,int}+R_{g,off}^{ext}+R_{drv,off},
$$

where $R_{g,int}=1\ \Omega$ for C2M0025120D. The parasitic defaults are example circuit assumptions, not guaranteed datasheet values; real layouts should supply measured or extracted values.

### Shared device relations

The device layer in [`device_data.py`](src/switching_loss_engine/models/device_data.py) uses PCHIP interpolation of the extracted datasheet curves. Its main relations are:

$$
R_{DS(on)}(T_j)=25\ \mathrm{m\Omega}
+(41-25)\ \mathrm{m\Omega}\frac{T_j-25}{125},
\qquad
V_{on}=\max\!\left(I_D R_{DS(on)},0.05\right).
$$

Threshold voltage $V_{th}(T_j)$ comes from Fig. 11. The Miller plateau estimate $V_{pl}(I_D,T_j)$ is obtained by inverting the temperature-interpolated Fig. 7 transfer characteristic. Capacitances are reconstructed from Figs. 17-18 as

$$
C_{gd}=C_{rss}, \qquad C_{gs}=C_{iss}-C_{rss}, \qquad C_{ds}=C_{oss}-C_{rss}.
$$

The dynamic Miller charge is anchored to the datasheet value $Q_{gd,ref}=71.5\ \mathrm{nC}$ at 800 V, 50 A, and 25 °C, while retaining the extracted $C_{gd}(V)$ voltage shape:

$$
Q_{gd,dyn}=Q_{gd,ref}
\frac{\int_{V_{on}}^{V_{dc}} C_{gd}(V)\,dV}
{\int_{50R_{DS(on)}(25^\circ\mathrm C)}^{800} C_{gd}(V)\,dV}.
$$

Reverse-recovery charge and time use two datasheet anchors and power-law interpolation. For charge,

$$
b_Q=\frac{\ln(Q_{rr,1}/Q_{rr,2})}{\ln(S_1/S_2)}, \qquad
Q_{rr}=Q_{rr,1}\left(\frac{|di/dt|}{S_1}\right)^{b_Q}\left(\frac{I_D}{50}\right),
$$

with $(Q_{rr,1},S_1)=(487\ \mathrm{nC},2180\ \mathrm{A/\mu s})$ and $(Q_{rr,2},S_2)=(386\ \mathrm{nC},1320\ \mathrm{A/\mu s})$. The same form, using the 33 ns and 67 ns anchors, gives $t_{rr}$. Internally, very small $|di/dt|$ is limited to $10^6\ \mathrm{A/s}$ for numerical robustness.

### M0: anchored datasheet loss surface

M0 is the fastest, data-driven model. It uses the 800 V, 50 A, 25 °C, 2.5 Ω table values

$$
E_{on,ref}=2.18\ \mathrm{mJ}, \qquad E_{off,ref}=0.68\ \mathrm{mJ}
$$

and multiplies independent voltage-current, temperature, and gate-resistance shape factors:

$$
E_{on}=E_{on,ref}K_{VI,on}K_{T,on}K_{Rg,on}, \qquad
E_{off}=E_{off,ref}K_{VI,off}K_{T,off}K_{Rg,off}.
$$

The factors are

$$
K_{VI,x}=\frac{E_x^{Fig.23/24}(V_{dc},I_D)}{E_x^{Fig.23/24}(800,50)}, \quad
K_{T,x}=\frac{E_x^{Fig.26}(T_j)}{E_x^{Fig.26}(25)},
$$

$$
K_{Rg,on}=\frac{t_r^{Fig.27}(R_{g,on}^{ext})}{t_r^{Fig.27}(2.5)}, \qquad
K_{Rg,off}=\frac{t_f^{Fig.27}(R_{g,off}^{ext})}{t_f^{Fig.27}(2.5)}.
$$

The voltage-current surface linearly interpolates between the 600 V and 800 V curves and uses PCHIP along current. M0 does not use circuit parasitics. It is restricted to 600-800 V and the overlapping Fig. 23/Fig. 24 current domain. Fig. 25 is deliberately not used because its extracted total-energy curve is inconsistent with `Eon + Eoff`.

### M1: gate-charge semi-analytical model

M1 estimates four transition durations. Current-rise and current-fall time integrate the extracted Fig. 12 gate-charge curve between $V_{th}$ and $V_{pl}$:

$$
t=\left|\int_{Q(V_a)}^{Q(V_b)}
\frac{R_g}{|V_{drive}-V_{gs}(Q)|}\,dQ\right|.
$$

The implementation limits the denominator to at least 0.2 V near a drive rail. The Miller intervals are

$$
t_{vf}=\frac{Q_{gd,dyn}}{(V_{g,on}-V_{pl})/R_{g,on}}, \qquad
t_{vr}=\frac{Q_{gd,dyn}}{(V_{pl}-V_{g,off})/R_{g,off}}.
$$

Assuming linear current or voltage motion in each interval, the raw overlap terms are

$$
E_{on,ir}=\tfrac12V_{dc}I_Dt_{ir}, \qquad
E_{on,vf}=\tfrac12(V_{dc}+V_{on})I_Dt_{vf},
$$

$$
E_{off,vr}=\tfrac12(V_{dc}+V_{on})I_Dt_{vr}, \qquad
E_{off,if}=\tfrac12V_{dc}I_Dt_{if}.
$$

With $E_{rr}=V_{dc}Q_{rr}$ and $E_{oss}$ interpolated from Fig. 16,

$$
E_{on,raw}=E_{on,ir}+E_{on,vf}+E_{rr}+E_{oss}, \qquad
E_{off,raw}=E_{off,vr}+E_{off,if}.
$$

M1 uses driver resistance but does not use $L_g$, $L_s$, $L_{loop}$, $R_{loop}$, or $\eta_{loop}$.

### M2: segmented quasi-analytical model with parasitics

M2 retains the M1 energy partition but modifies transition timing and stress estimates. During a current-changing interval,

$$
R_{eff,0}(V_{gs})=R_g+\frac{L_s g_m(V_{gs},T_j)}{C_{iss}}, \qquad
t_0=\left|\int_{V_a}^{V_b}\frac{R_{eff,0}C_{iss}}{|V_{drive}-V_{gs}|}\,dV_{gs}\right|.
$$

Gate inductance is represented as the stage-frequency effective resistance

$$
R_{Lg}=\frac{L_g}{\max(t_0,0.5\ \mathrm{ns})}, \qquad
t=\left|\int_{V_a}^{V_b}\frac{(R_{eff,0}+R_{Lg})C_{iss}}{|V_{drive}-V_{gs}|}\,dV_{gs}\right|.
$$

For a Miller interval, $t_0=Q_{gd,dyn}R_g/\Delta V_g$ and

$$
t_M=\frac{Q_{gd,dyn}(R_g+L_g/\max(t_0,0.5\ \mathrm{ns}))}{\Delta V_g}.
$$

The derived slew rates and peak stresses are

$$
\left|\frac{di}{dt}\right|=\frac{I_D}{t_i}, \qquad
\left|\frac{dv}{dt}\right|=\frac{V_{dc}-V_{on}}{t_v},
$$

$$
I_{rr,pk}=\frac{2Q_{rr}}{t_{rr}}, \quad
I_{D,pk}=I_D+I_{rr,pk}, \quad
V_{DS,pk}=\min\!\left(1200,V_{dc}+L_{loop}|di/dt|_{off}\right).
$$

M2 adds an allocated part of the loop magnetic energy:

$$
E_{loop,on}=\eta_{loop}\tfrac12L_{loop}\max(I_{D,pk}^2-I_D^2,0), \qquad
E_{loop,off}=\eta_{loop}\tfrac12L_{loop}I_D^2.
$$

Its raw turn-on energy is the M1 turn-on sum plus $E_{loop,on}$. Turn-off uses

$$
E_{off,if}=\tfrac14(V_{dc}+V_{DS,pk})I_Dt_{if}
$$

instead of the M1 current-fall term, and adds $E_{loop,off}$. M2 uses $R_{drv}$, $L_s$, $L_g$, $L_{loop}$, and $\eta_{loop}$; the current implementation does not use `rloop_ohm` until M3.

### M3: stage-continuous virtual double-pulse solver

M3 is a reduced-order time-domain solver. Turn-on is split into `gate_delay`, `current_rise`, `reverse_recovery`, and `voltage_fall`; turn-off is split into `gate_discharge`, `voltage_rise`, and `current_fall`. Time is continuous across stages.

The gate loop follows

$$
L_g\frac{di_g}{dt}=V_{drive}-V_{gs}-R_gi_g-V_{Ls}, \qquad
C_{iss}\frac{dV_{gs}}{dt}=i_g,
$$

where $V_{Ls}=L_s\widehat{di_D/dt}$ and $\widehat{di_D/dt}=g_mi_g/C_{iss}$. With backward Euler for the resistance term,

$$
i_g^{n+1}=\frac{i_g^n+\Delta t(V_{drive}-V_{gs}^n-V_{Ls})/L_g}
{1+\Delta t R_g/L_g}, \qquad
V_{gs}^{n+1}=V_{gs}^n+\Delta t\frac{i_g^{n+1}}{C_{iss}}.
$$

Channel current is calculated from the interpolated transfer characteristic with a smooth saturation-to-ohmic transition:

$$
I_{ch}=I_{sat}(V_{gs},T_j)\tanh\!\left(
\frac{V_{ds}}{R_{DS(on)}(T_j)I_{sat}(V_{gs},T_j)}\right).
$$

During turn-on current rise, the loop equation is approximated by

$$
V_{ds}=\mathrm{clip}\!\left(V_{dc}-R_{loop}I_D-L_{loop}\max(di_D/dt,0),V_{on},V_{dc}\right).
$$

Reverse recovery is a triangular current pulse with area $Q_{rr}$ and duration $t_{rr}$. During turn-off current fall,

$$
V_{ds}=\min\!\left(1200,V_{dc}+R_{loop}I_D+L_{loop}|\min(di_D/dt,0)|\right).
$$

The voltage-transition stages integrate $dV_{ds}/dt=\mp i_g/C_{gd}^{*}(V)$, where

$$
C_{gd}^{*}(V)=C_{gd}(V)\frac{Q_{gd,dyn}}
{\int_{V_{on}}^{V_{dc}}C_{gd}(V)\,dV}.
$$

Raw event energy comes directly from the generated waveforms plus allocated loop energy:

$$
E_{on,raw}=\int V_{ds}(t)I_D(t)\,dt
+\eta_{loop}\tfrac12L_{loop}\max(I_{D,pk}^2-I_D^2,0),
$$

$$
E_{off,raw}=\int V_{ds}(t)I_D(t)\,dt
+\eta_{loop}\tfrac12L_{loop}I_D^2.
$$

M3 does not add a separate $E_{oss}$ term; its reported components are turn-on overlap, turn-on loop, turn-off overlap, and turn-off loop. It reports whether every stage terminated, whether all values are finite, whether time is continuous, and how many steps each stage used. With the default convergence check, the calculation is repeated at $\Delta t/2$ and accepted only when both raw-energy relative changes are at most 8%.

### Fixed calibration profiles

M1-M3 apply explicit, versioned profiles after calculating raw energy:

$$
E_x=E_{x,raw}\,S_x\,F_{I,x}(I_D)\,F_{T,x}(T_j), \qquad x\in\{on,off\}.
$$

The correction factors are linearly interpolated from immutable YAML tables and held at the nearest endpoint outside their tabulated range. They are never fitted again during prediction.

| Model | Default profile | Absolute scale $(S_{on},S_{off})$ | Reference |
|---|---|---:|---|
| M0 | none | not applicable | direct 800 V/50 A datasheet anchor |
| M1 | `m1_reference_v1` | (1.563698, 0.838435) | 800 V, 50 A, 25 °C, 2.5 Ω |
| M2 | `m2_reference_v1` | (1.445316, 0.663325) | 800 V, 50 A, 25 °C, 2.5 Ω |
| M3 | `m3_phase5_xml_shape_v1` | (0.543901, 0.251775) | manufacturer XML, 800 V, 48.07 A, 25 °C, 5 Ω; fixed current and temperature corrections |

M3 also provides `m3_datasheet_table_v1` with scales (0.885122, 0.953311) for reproducing the 800 V, 50 A, 25 °C, 2.5 Ω datasheet table anchor. Exact correction grids and provenance are stored under [`device_library/.../calibration`](src/powersemiforge/device_library/wolfspeed/C2M0025120D/calibration/).

Changing parasitics does not change a calibration profile. The raw equations respond to the new parasitics, the same fixed correction is applied, and the API emits a warning if the parasitics differ from the profile reference. This prevents operating-point-specific refitting from being mistaken for a global calibration.

### Output contract and model selection

Every model returns the same top-level [`CalculationResult`](src/switching_loss_engine/schemas.py): input echo, calibrated energies, timing, electrical stress, component energies, solver state, provenance, warnings, and an uncertainty field. M3 can additionally return turn-on and turn-off waveform samples containing time, stage, $V_{gs}$, $V_{ds}$, $I_D$, $I_g$, instantaneous power, and turn-on recovery current.

The current `relative_95_pct` values (M0 18%, M1 28%, M2 26%, M3 32%) are model-form allowances based on datasheet/XML holdout evidence; they are not a per-run probabilistic propagation. Use M0 for fast in-domain sweeps, M1 for explainable gate-charge estimates, M2 for analytical parasitic sensitivity, and M3 when stage waveforms, solver status, and explicit loop dynamics are required.

These are engineering reduced-order models. Results outside the direct 600-800 V and 12.56-60 A switching-energy evidence domain are flagged, and all safety-critical use requires independent double-pulse measurement validation.

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
Plan/Active/                    at most one currently executing plan
Plan/Completed/                 archived plans whose work is finished
```

## Reproducibility rules

1. Every source file is identified by SHA-256.
2. Every extracted value retains its source, page or locator, units, conditions, extractor version, and confidence.
3. Calibration profiles are immutable YAML artifacts; models never refit themselves during prediction.
4. Calibration and holdout points are explicitly separated.
5. A batch run receives a deterministic ID from its canonical matrix configuration.
6. Failures are recorded per source or operating point rather than silently dropped.
7. At most one Markdown plan may exist in `Plan/Active`; completed plans are moved to `Plan/Completed`.

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
