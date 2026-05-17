---
layout: default
---

# Roadmap

## v1.0 Scope

- JSON project schema with provenance.
- CSV curve import for digitized capacitance plots.
- Built-in `vdmos-static-fast` and `abm-basic` emitters.
- LTspice, ngspice, common, PSpice, HSPICE, Xyce, and experimental QSPICE
  starter decks.
- Plugin entry points for third-party extractors, validators, and emitters.
- Unit tests, CI, examples, and license documentation.

## Near-Term Improvements

- Raster-plot digitization for scanned datasheets.
- More validators for gate charge, diode curves, and switching-test conditions.
- ngspice batch smoke tests for generated starter decks, followed by optional
  smoke-test adapters for PSpice/HSPICE/Xyce/QSPICE when local tools are
  available.
- Smoothing and charge-based capacitance functions for the ABM emitter.
- Parameter-fitting helpers that use measured double-pulse waveforms.

## Later Model Families

- Electrothermal ABM models.
- Verilog-A/OpenVAF model emitters when license and toolchain boundaries are clear.
- Library-quality example devices whose datasheet data is explicitly redistributable.
- GUI or local web workflow for guided datasheet review and curve import.
