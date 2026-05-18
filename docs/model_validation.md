---
layout: default
---

# Model Validation

`datasheet2spice` treats extraction and model generation as measurable
engineering tasks. A model is not considered good because a netlist was emitted;
it must pass repeatable compatibility, accuracy, convergence, and speed checks.

## Validation Layers

1. **Datasheet compatibility**: score extracted `DeviceProject` values against
   golden cases from many vendors and datasheet layouts.
2. **Dialect compatibility**: emit each model family for common SPICE, LTspice,
   ngspice, PSpice, HSPICE, Xyce, and QSPICE.
3. **Simulator convergence**: run available simulator decks and record return
   code, fatal log markers, warning count, and elapsed time.
4. **Accuracy**: compare simulated metrics against datasheet curves, vendor
   SPICE models, or measured waveforms.
5. **Regression**: keep every result as JSON/Markdown evidence so future model
   changes can be compared to the previous baseline.

## Datasheet Case Manifests

Public regression candidates live under `validation/`. The repository stores
metadata, URLs, expected values, and tolerance rules, not copies of vendor PDFs.
Downloaded PDFs and vendor model ZIPs should stay in a local cache.

Score a project against a golden case:

```powershell
datasheet2spice score-case examples/demo_sic_diode/device.json validation/golden/demo_sic_diode.case.json --format md
```

A case can mark critical fields with `required_fields`. Any required-field
failure makes the case fail even if the aggregate score is high.

## Model Benchmarks

Generate a benchmark evidence pack without running a simulator:

```powershell
datasheet2spice benchmark-model examples/demo_sic_diode/device.json `
  --out build/bench-diode `
  --model diode-basic `
  --model diode-abm-dynamic `
  --dialect all
```

This creates generated netlists plus:

- `benchmark_report.json`
- `benchmark_report.md`

When LTspice is installed, run convergence and speed smoke checks:

```powershell
datasheet2spice benchmark-model examples/demo_sic_diode/device.json `
  --out build/bench-diode-ltspice `
  --model diode-abm-dynamic `
  --dialect ltspice `
  --run-ltspice `
  --ltspice "C:\Users\<user>\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
```

The current benchmark schema records generation success, simulator status,
elapsed time, fatal log markers, and warnings. Future benchmark adapters can add
ngspice, Xyce, HSPICE, PSpice, and waveform metric extraction without changing
the top-level evidence shape.

## Accuracy Targets

Starter acceptance targets should be conservative at first:

- table-field extraction: required values pass within declared tolerance,
- curve digitization: log-domain RMS error under 10-20% for clean vector plots,
- diode `VF(IF)` and MOSFET `RDS(on)`: 5-10% after fitting,
- capacitance curves: 15-25% before lab fitting,
- diode reverse recovery: 20-40% starter error, then tighter after waveform
  fitting,
- convergence: no systematic fatal simulator failures for the public regression
  set.

Vendor SPICE models are useful baselines when their licenses allow local use,
but generated results should still be compared to datasheet test conditions and
lab waveforms before design use.

## Adding A New Case

1. Add a JSON case or manifest entry under `validation/`.
2. Include vendor, part numbers, component profile, source URL, layout tags,
   expected fields, tolerances, and reference model availability.
3. Cache the PDF locally and run extraction.
4. Save the generated project JSON.
5. Run `score-case`.
6. Run `benchmark-model` for the relevant emitters and dialects.
7. Attach result JSON/Markdown to the evidence pack for the release or pull
   request.

