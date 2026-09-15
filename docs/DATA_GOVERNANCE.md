# Data governance

PowerSemiForge source code is MIT licensed. That license does not grant redistribution rights for manufacturer PDFs, XML/SPICE models, logos, or extracted datasets.

Repository defaults:

- Ignore raw PDFs and manufacturer XML files.
- Commit hashes and source citations instead of raw documents when redistribution is unclear.
- Publish extracted numeric data only after reviewing the source terms.
- Never mix confidential lab data with public example datasets.
- Record whether each asset is manufacturer data, measured data, synthetic data, or a fitted derivative.
- Keep calibration and holdout provenance separate.

Before a public release, run `git status --ignored` and review every device-library asset manually.

