# C2M0025120D example dataset card

## Purpose

This device is the first calculation-ready PowerSemiForge example and exercises extraction, fixed calibration, M0-M3 calculation, batch execution, validation, and plotting.

## Sources

- Wolfspeed C2M0025120D datasheet, identified locally by SHA-256 in the extraction artifacts and project baseline.
- Manufacturer PLECS XML used locally to derive the versioned XML calibration/holdout dataset.
- Vector-extracted curve CSV files listed in the device manifest.

Raw PDF and manufacturer XML files are not intended for Git publication. The XML path is ignored and represented by an empty tracked directory.

## Validation boundary

- M0-M2 reproduce the selected datasheet reference anchor.
- Default M3 uses a separate manufacturer-XML calibration profile.
- M3 holdout points are separated from calibration points, but both remain within the same manufacturer evidence family.
- No independent double-pulse measurement dataset is included.

## Redistribution review

The repository's MIT License applies to source code only. Before publishing the extracted CSV files or derived XML validation values, the maintainer must review the applicable manufacturer terms and decide whether those data files may be redistributed.

