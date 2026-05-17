# Roadmap

## v1.0 Scope

- JSON project schema with provenance.
- CSV curve import for digitized capacitance plots.
- Built-in `vdmos-static-fast` and `abm-basic` emitters.
- LTspice/ngspice/common starter decks.
- Plugin entry points for third-party extractors, validators, and emitters.
- Unit tests, CI, examples, and license documentation.

## Near-Term Improvements

- CLI wrappers for optional PDF vector extraction.
- More validators for gate charge, diode curves, and switching-test conditions.
- ngspice batch smoke tests for generated starter decks.
- Smoothing and charge-based capacitance functions for the ABM emitter.
- Parameter-fitting helpers for double-pulse waveforms.

## Later Model Families

- Electrothermal ABM models.
- Verilog-A/OpenVAF model emitters when license and toolchain boundaries are clear.
- Library-quality example devices whose datasheet data is explicitly redistributable.
- GUI or local web workflow for guided datasheet review and curve import.
