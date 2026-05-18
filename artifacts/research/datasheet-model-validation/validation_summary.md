# Datasheet Model Validation Evidence

Status: initial validation harness implemented.

## Hypothesis

Model compatibility, accuracy, convergence, and speed can be improved only if
each extractor/model change is measured against repeatable public datasheet
cases and simulator benchmark records.

## Current Evidence

- Local tool probe: completed during development; keep machine-specific probe
  files under `artifacts/local/` instead of committing workstation paths.
- LTspice smoke benchmark: `ltspice-smoke-benchmark.json`.
- All-dialect generation benchmark: `all-dialects-generation-benchmark.json`.
- Demo extraction golden case: `validation/golden/demo_sic_diode.case.json`.
- Public datasheet regression candidates:
  `validation/public_datasheet_cases.json`.

## Completed Smoke Result

The demo diode `diode-basic` and `diode-abm-dynamic` LTspice decks both ran
successfully on this machine.

- Simulated decks: 2
- Failed simulations: 0
- Mean elapsed time: 0.5818 s
- Warning count: 0 for both decks
- All-dialect generated files: 28

This is a smoke result, not a waveform-accuracy claim. The next evidence level
is to compare simulated `VF(IF)`, `Cj(VR)`, `trr`, `Qrr`, `Irrm`, and switching
energy against vendor datasheet curves or vendor SPICE models.
