---
layout: default
---

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

## Diode Basic

The `diode-basic` emitter writes a portable two-terminal subcircuit around a
native SPICE `D` model card. It maps datasheet values into starter parameters:

- `BV` from `VRRM` or reverse-voltage rating.
- `Rs`, `Is`, and `N` from a forward-voltage point and reference current.
- `Cjo` from junction or total capacitance.
- `Tt` from `Qrr/IF` or `trr`.
- `Ibv` from reverse leakage current when available.
- anode and cathode lead inductance/resistance from package parasitics or
  conservative defaults.

The generated diode model is intentionally compact and portable. It is suitable
for early topology checks and first transient comparisons, then should be fitted
against datasheet `VF(IF)`, `Cj(VR)`, thermal, and recovery curves.

## Diode ABM Dynamic

The `diode-abm-dynamic` emitter keeps the portable two-terminal package shell
but adds behavioral transient terms:

- a smoothed nonlinear `Cj(VR)` current source using `CJO`, `VJ`, `M`, and
  `CJ_SCALE`,
- a hidden `qrr_state` capacitor that stores forward-conduction recovery charge,
- a smoothed reverse-bias gate that releases the stored charge as recovery
  current using `TAU` and `RR_SCALE`,
- the same DC diode card, leakage path, and package parasitics used by the
  compact diode starter.

The starter fit maps `CJO_pF`, `TRR_ns`, `QRR_nC`, and `IRRM_A` into initial
`TAU_ns`, `RR_SCALE`, and `CJ_SCALE` values. This can produce more realistic
reverse-recovery transients than a plain diode `TT` card, but it is still a
reviewable approximation. Tune it against datasheet recovery test conditions or
measured waveforms before relying on switching-loss predictions.

## Model Level Naming

This project avoids `L1/L2/L3` names because they conflict with:

- SPICE `LEVEL=` model equations,
- vendor-specific model-level definitions.

Instead use:

- `model_class`: `vdmos`, `abm`, `verilog_a`
- `fidelity`: `static`, `dynamic`, `electrothermal`, `lab_fitted`
