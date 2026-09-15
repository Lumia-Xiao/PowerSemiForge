# Contributing

Use Python 3.10 or newer. Install `.[pdf]`, run `python -m unittest discover -s tests -v`, and include tests for every extractor, device, model, and output-schema change.

Contributions must:

- retain source hashes and extraction provenance;
- use SI units at API boundaries;
- avoid runtime calibration or silent extrapolation;
- record per-item failures in batch operations;
- avoid committing raw manufacturer documents without confirmed redistribution rights;
- keep generated results, environments, and caches out of Git.

Open an issue before making incompatible schema changes.

