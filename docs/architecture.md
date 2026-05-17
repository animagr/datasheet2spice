# Architecture

`datasheet2spice` is split into small, replaceable layers.

```text
datasheet / CSV / manual corrections
        |
        v
ingest + extractors
        |
        v
DeviceProject JSON schema
        |
        v
fitters
        |
        v
emitters
        |
        v
validators + reports
```

## Core Rules

- The core package is dependency-free.
- Optional PDF and simulator integrations live behind plugin boundaries.
- Every extracted number should have provenance.
- Generated models are starters, not vendor-qualified models.

## Model Classes

`vdmos-static-fast`

- Built-in compact model starter.
- Intended for speed and early power-stage sweeps.

`abm-basic`

- Behavioral subcircuit starter.
- Intended for datasheet curve fitting and transient waveform exploration.

Future:

- `abm-electrothermal`
- `verilog-a-dynamic`
- `lab-fitted`
