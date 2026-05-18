---
layout: default
---

# Roadmap

## v1.0 Scope

- JSON project schema with provenance.
- Backward-compatible `DeviceProject` plus the broader `ComponentProject`
  direction.
- Runtime mode contract for static browser files and the local Python backend.
- Component profile registry, starting with `mosfet.power` and `diode.power`.
- CSV curve import for digitized capacitance plots.
- Built-in `vdmos-static-fast`, `abm-basic`, `diode-basic`, and
  `diode-abm-dynamic` emitters.
- LTspice, ngspice, common, PSpice, HSPICE, Xyce, and experimental QSPICE
  starter decks.
- Extraction scoring and model benchmark evidence commands.
- Opt-in plugin entry points for trusted third-party extractors, validators,
  and emitters.
- Unit tests, CI, examples, and license documentation.

## Near-Term Improvements

- Split the current workbench into a TypeScript frontend and a local service
  adapter while preserving the static browser demo.
- Move browser-heavy helpers into Web Workers and later Rust/WASM modules.
- Raster-plot digitization for scanned datasheets.
- More validators for gate charge, diode curves, and switching-test conditions.
- ngspice batch smoke tests for generated starter decks, followed by waveform
  metric extraction and optional adapters for PSpice/HSPICE/Xyce/QSPICE when
  local tools are available.
- Smoothing and charge-based capacitance functions for the ABM emitter.
- Parameter-fitting helpers that use measured double-pulse waveforms.

## Later Model Families

- Lab-fitted power diode behavioral and electrothermal starters.
- IGBT starter models.
- BJT and signal diode model starters.
- Guided tool panels for gate-drive, thermal, double-pulse, and parasitic
  calculations.
- Electrothermal ABM models.
- Verilog-A/OpenVAF model emitters when license and toolchain boundaries are clear.
- Library-quality example devices whose datasheet data is explicitly redistributable.
