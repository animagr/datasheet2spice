# Modeling Notes

## VDMOS

The `vdmos-static-fast` emitter maps datasheet values into a compact power MOSFET model starter.

Typical mapping:

- `Vto`: threshold voltage.
- `Kp`: transconductance starter from `gfs` and `RDS(on)`.
- `Rd/Rs`: split from `RDS(on)`.
- `Rg`: internal gate resistance.
- `Cgs`: high-voltage `Ciss - Crss`.
- `Cgdmin`: high-voltage `Crss`.
- `Cgdmax`: low-voltage `Crss`.
- `Cjo`: high-voltage `Coss - Crss`.
- `Tt`: reverse recovery starter from `Qrr/IF` or `trr`.

For `ltspice` and `ngspice`, this is emitted as a native `.model ... VDMOS(...)`
card. For `common`, `pspice`, `hspice`, `xyce`, and experimental `qspice`, the
emitter writes a portable MOS fallback subcircuit with fixed capacitances and a
simple `NMOS LEVEL=1` channel. The fallback is useful for topology and deck
checks, but it is not equivalent to a native VDMOS implementation.

This family is fast, but not enough for high-fidelity switching waveforms without fitting.

## ABM Basic

The `abm-basic` emitter uses:

- smooth `Idsat(Vgs)` plus `RDS(on)` channel current,
- nonlinear `Cgs/Cgd/Cds` from datasheet capacitance curves,
- simple body diode,
- explicit package/gate parasitics.

The current capacitance implementation is a starter. For better convergence and accuracy, future work should replace table capacitances with smoothed charge functions.

See [SPICE Dialects](spice_dialects.md) for the supported netlist dialects and
the boundary between native VDMOS and portable fallback exports.

## Model Level Naming

This project avoids `L1/L2/L3` names because they conflict with:

- SPICE `LEVEL=` model equations,
- vendor-specific model-level definitions.

Instead use:

- `model_class`: `vdmos`, `abm`, `verilog_a`
- `fidelity`: `static`, `dynamic`, `electrothermal`, `lab_fitted`
