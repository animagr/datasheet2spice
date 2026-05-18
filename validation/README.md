# Validation Assets

This directory defines the repeatable quality loop for datasheet extraction and
SPICE model generation.

The repository stores metadata and golden values, not third-party datasheet PDF
copies. Public PDFs and vendor SPICE models should be downloaded into a local
cache such as `tmp/validation-cache/` before running extraction benchmarks.

## Quality Gates

1. **Extraction compatibility**: score a generated `DeviceProject` against a
   golden case file.
2. **Model generation compatibility**: emit each model family across the major
   SPICE dialects.
3. **Simulator convergence**: run available simulator decks and record
   return code, fatal log markers, warnings, and elapsed time.
4. **Model accuracy**: compare simulated metrics against datasheet curves,
   extracted golden values, vendor models, or measured waveforms.

## Commands

Score one extracted project:

```powershell
datasheet2spice score-case examples/demo_sic_diode/device.json validation/golden/demo_sic_diode.case.json --format md
```

Generate benchmark evidence without running a simulator:

```powershell
datasheet2spice benchmark-model examples/demo_sic_diode/device.json --out build/bench-diode --model diode-basic --model diode-abm-dynamic --dialect all
```

Run LTspice smoke benchmarks when LTspice is available:

```powershell
datasheet2spice benchmark-model examples/demo_sic_diode/device.json --out build/bench-diode-ltspice --model diode-abm-dynamic --dialect ltspice --run-ltspice --ltspice "C:\Users\<user>\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
```

## Manifest Policy

Each public case should capture:

- source URL and license notes,
- vendor, part number, component profile, and datasheet layout tags,
- whether it is a single-part or series datasheet,
- expected fields with absolute or relative tolerances,
- reference model availability,
- target simulation benches and accuracy metrics.

