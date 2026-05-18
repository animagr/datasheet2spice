---
layout: default
---

# SPICE Dialects

`datasheet2spice` keeps one internal device project and exports simulator
specific netlists through emitter dialects.

Supported dialect names:

- `common`: conservative portable SPICE starter.
- `ltspice`: LTspice-oriented behavioral sources and native VDMOS model card.
- `ngspice`: ngspice/SPICE3-oriented behavioral sources and native VDMOS model card.
- `pspice`: PSpice-style `VALUE` controlled-source ABM starter.
- `hspice`: HSPICE-style expression-current-source ABM starter.
- `xyce`: Xyce/SPICE3 behavioral-source ABM starter.
- `qspice`: experimental LTspice-like ABM starter for QSPICE review.

Use all built-in dialects:

```powershell
datasheet2spice emit examples/demo_sic_mosfet/device.json --out build/demo --all --dialect all
```

## Model Family Coverage

`abm-basic` supports every dialect above. It emits a three-pin subcircuit with
smooth channel current, datasheet capacitance tables, body diode, and starter
package parasitics.

`vdmos-static-fast` has two export modes:

- `ltspice` and `ngspice`: native `.model ... VDMOS(...)` card plus a starter
  double-pulse deck.
- `common`, `pspice`, `hspice`, `xyce`, and `qspice`: portable MOS fallback
  subcircuit using a simple `NMOS LEVEL=1` channel, body diode, fixed
  capacitances, and parasitics. This keeps file generation and early topology
  checks portable, but it is not a native VDMOS model.

`diode-basic` supports every dialect above with a portable two-terminal
subcircuit and native `.model ... D(...)` card. The same generated core model is
used across dialects because the SPICE diode primitive is widely supported.

`diode-abm-dynamic` supports every dialect above with a two-terminal subcircuit
that combines a DC diode card with behavioral current sources for nonlinear
`Cj(VR)` and reverse-recovery charge release. It uses `VALUE`, `CUR`, or
SPICE3-style `B` source syntax according to the selected dialect, so simulator
expression compatibility matters more than it does for `diode-basic`.

## Accuracy Notes

Dialect support means the emitter writes a netlist in the syntax family of the
target simulator. It does not mean the model is vendor-qualified or fully
calibrated.

For transient accuracy, prefer:

1. `abm-basic` for cross-dialect behavior review.
2. `vdmos-static-fast` native LTspice/ngspice for fast compact-model sweeps.
3. `diode-basic` for compact diode smoke checks.
4. `diode-abm-dynamic` when recovery charge and junction capacitance need to
   shape transient waveforms before a lab-fitted model exists.
5. Measured double-pulse or curve fitting before design use.

The `qspice` dialect is intentionally marked experimental until it is backed by
automated QSPICE smoke tests.
