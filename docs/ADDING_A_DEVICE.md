# Adding a device

1. Run `psforge device scaffold --library workspace/device_library --vendor <vendor> --part <part>`.
2. Put raw PDFs/XML under `workspace/`; these paths are ignored by Git.
3. Run the PDF/XML extractors and review warnings, units, conditions, duplicate values, and source locations.
4. Promote reviewed curves and parameters into the device manifest.
5. Run `psforge model scaffold --device-dir <path> --model-id M0`, then replace the explicit `NotImplementedError` with traceable equations. The tool deliberately scaffolds code rather than inventing a physical model from sparse PDF values.
6. Create an immutable calibration YAML. Never calculate calibration scales in a prediction method.
7. Freeze calibration and holdout datasets before reporting errors.
8. Add unit, reference-point, solver-convergence, and holdout regression tests.

Do not report a device as calculation-ready until the manifest, required curves, calibration profile, domain limits, and validation status are all explicit.
