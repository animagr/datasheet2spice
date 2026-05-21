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
elapsed time, fatal log markers, and warnings. For LTspice MOSFET double-pulse
decks, add switching metrics with:

```powershell
datasheet2spice benchmark-model examples/demo_sic_mosfet/device.json `
  --out build/bench-mosfet-switching `
  --model abm-basic `
  --model vdmos-static-fast `
  --dialect ltspice `
  --measure-switching `
  --run-ltspice `
  --ltspice "C:\Users\<user>\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
```

`--measure-switching` instruments generated MOSFET double-pulse decks with
LTspice `.meas` statements and records:

- average gate high and gate low levels,
- average on-state load current,
- average and minimum on-state drain voltage,
- second-pulse re-on drain voltage,
- turn-off drain overshoot,
- turn-off drain peak-to-peak ringing,
- simulation elapsed time, warnings, fatal markers, and return code.

The benchmark flags hard failures such as gate drive not reaching the on level,
load current not building, the drain not pulling low, excessive overshoot, and
severe turn-off ringing. It also checks that the second pulse pulls the drain
low again, which catches slow or unstable re-on behavior that can be hidden by
first-pulse averages. Moderate turn-off ringing is marked as `review` so a human
can compare the waveform against datasheet or bench conditions.

Future benchmark adapters can add ngspice, Xyce, HSPICE, PSpice, vendor `.lib`
reference comparisons, and raw-waveform metric extraction without changing the
top-level evidence shape.

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

When a generated MOSFET does not turn on or shows unstable turn-off ringing,
use this order:

1. Re-run `benchmark-model --measure-switching` on the generated ABM and VDMOS
   models to separate extraction/model issues from simulator setup issues.
2. Compare `V(gate)`, `I(Lload)`, `V(drain)`, and elapsed time against a vendor
   `.lib` under the same external circuit when the license permits local use.
3. Check whether the datasheet only covers typical static values; if so, add a
   same-vendor reference device with a trusted `.lib` to calibrate missing
   channel, capacitance, body-diode, and parasitic assumptions.
4. Treat agreement with a vendor `.lib` as an engineering baseline, not final
   truth; close the loop with measured double-pulse waveforms before claiming
   accuracy.

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
