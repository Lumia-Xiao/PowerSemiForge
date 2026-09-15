# Plan workflow

- `Active/` contains zero or one Markdown plan for work currently being executed.
- A new plan may be added only when `Active/` contains no other Markdown plan.
- When all acceptance checks pass, change the plan status to `COMPLETED` and move it to `Completed/` with a descriptive filename.
- Historical plans are immutable evidence. Amend them only to correct an objective factual error.

The test suite enforces the zero-or-one Active plan rule.
