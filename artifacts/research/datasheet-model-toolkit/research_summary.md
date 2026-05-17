# Datasheet-to-SPICE behavioral model toolkit research summary

Date: 2026-05-17

## Question

Are there open-source toolkits that extract parameters from datasheets and construct device behavioral models, especially for power MOSFET/SiC transient SPICE simulation? If not, can we build one?

## Short Answer

I did not find a mature open-source end-to-end tool that takes a MOSFET/SiC MOSFET PDF datasheet and automatically outputs a validated, high-accuracy, fast-converging SPICE transient behavioral model.

The ecosystem has useful open-source pieces:

- plot digitizers
- PDF/vector extraction libraries
- SPICE netlist editors and simulation wrappers
- Verilog-A/OpenVAF/ngspice model infrastructure
- public papers describing datasheet-driven extraction algorithms

Commercial tools already offer similar workflows, especially MATLAB/Simscape and SIMetrix/SIMPLIS, but they are not open-source.

This means building our own toolkit is feasible and useful. The S4661 work already contains a small seed implementation.

## Existing Open-Source Pieces

### Curve/data extraction

- WebPlotDigitizer: https://github.com/automeris-io/WebPlotDigitizer
  - Frontend is GNU AGPL v3.
  - AI Assist/cloud systems are closed source.
  - Good for manual/semi-automatic digitization.

- StarryDigitizer: https://digitizer.starrydata.org/
  - Browser-based, open-source graph value extraction.
  - Useful for curve extraction when PDF vector paths are not available.

- PyMuPDF/fitz
  - Not specifically a datasheet-modeling tool, but works well for extracting text, vector paths, and page renders from PDFs.
  - In S4661, Fig.19 capacitance curves were extracted directly from PDF vector paths, better than raster tracing.

### SPICE generation and simulation automation

- PySpice: https://github.com/PySpice-org/PySpice
  - Python interface to ngspice and Xyce.
  - Supports netlists, simulation, numpy export, plotting, and some parsing.
  - Useful for automated validation loops, but it is not a datasheet-to-model extractor.

- spicelib / PyLTSpice SpiceEditor: https://pyltspice.readthedocs.io/en/latest/classes/spice_editor.html
  - Can manipulate SPICE netlists and read waveforms.
  - Useful for parameter sweeps and LTspice/QSPICE/ngspice automation.

- ngspice model infrastructure: https://ngspice.sourceforge.io/modelparams.html
  - Supports `.model` parameter sets and `.subckt` macro models.
  - Some vendor models are compatible; encrypted models are a limitation.

### Open compact-model infrastructure

- OpenVAF: https://openvaf.github.io/
  - Open-source Verilog-A compiler.
  - Compiles Verilog-A compact models for simulators that support OSDI.

- ngspice OSDI/OpenVAF: https://ngspice.sourceforge.io/osdi.html
  - ngspice can load OpenVAF-compiled Verilog-A compact device models at runtime.

- VA-Models: https://github.com/dwarning/VA-Models
  - Collection of Verilog-A compact models for ngspice/Xyce.
  - Useful as infrastructure and style reference, not a datasheet extractor.

## Commercial or Non-Open Reference Workflows

- MATLAB/Simscape Graph Data Extractor MOSFET example:
  https://www.mathworks.com/help/sps/ug/extract-mosfet-data-from-data-sheet.html
  - Shows exactly the workflow: extract MOSFET I-V, diode I-V, and switching-loss curves from datasheet plots.
  - Commercial, not open-source.

- SIMetrix/SIMPLIS MOSFETs from datasheets:
  https://deworde.simplistechnologies.com/documentation/simplis/sp_semi/topics/mosfet_models.htm
  - Has a "Create from Datasheet" workflow and PWL model extraction.
  - Commercial/license-gated.

## Algorithm References

- ORNL, Datasheet Driven Silicon Carbide Power MOSFET Model:
  https://www.osti.gov/biblio/1136644
  - Presents a datasheet-driven parameter extraction strategy requiring only datasheet data.
  - Validates dc, C-V, and switching characteristics.

- PSPICE compact model for power MOSFET based on manufacturer datasheet:
  https://doi.org/10.1088/1757-899X/948/1/012007
  - Describes parameter extraction for a PSpice compact power MOSFET model from datasheet data.

## Gap

The missing open-source package is the integration layer:

1. Parse datasheet text/tables.
2. Detect and digitize curves.
3. Normalize extracted curves into a device-parameter schema.
4. Fit model functions with physical constraints.
5. Generate simulator-specific SPICE/Verilog-A models.
6. Run validation decks and score against datasheet curves.
7. Produce a traceable evidence report.

Existing tools cover individual steps but not the complete pipeline for power MOSFET/SiC transient behavior.

## Proposed Toolkit

Working name: `datasheet2spice`.

### CLI

```powershell
datasheet2spice init S4661 TK-S4661_Rev.T17.2.pdf
datasheet2spice extract S4661.yml --fig capacitance --page 11
datasheet2spice fit S4661.yml --target dynamic-fast
datasheet2spice emit S4661.yml --dialect ltspice
datasheet2spice validate S4661.yml --sim ltspice --deck double-pulse
datasheet2spice report S4661.yml
```

### Package modules

- `pdf_ingest`
  - PyMuPDF text, tables, vector paths, raster renders.
  - Optional OCR fallback.

- `curve_digitizer`
  - Vector-path extraction when possible.
  - Raster color/edge tracing when vector paths are unavailable.
  - Manual WebPlotDigitizer/StarryDigitizer CSV import.

- `schema`
  - YAML/JSON device schema with provenance for every value.
  - Stores ratings, static curves, capacitance curves, gate charge, diode, switching loss, parasitics, thermal data.

- `fitters`
  - Smooth `RDS(on)(T)`, `Vth(T)`, `Idsat(Vgs,T)`.
  - `Ciss/Coss/Crss` smoothing and optional charge-function integration.
  - Diode and reverse-recovery starter fits.

- `emitters`
  - Common ABM SPICE.
  - LTspice.
  - ngspice.
  - Verilog-A/OpenVAF target for higher-performance open-source simulation.
  - Optional physical/compact-model backends, such as LTspice/ngspice VDMOS or OpenVAF Verilog-A compact models, when the available parameters are sufficient.

- `validators`
  - DC transfer/output checks.
  - C-V and Qg reconstruction checks.
  - Double-pulse transient checks.
  - Convergence/runtime metrics.

- `reports`
  - Markdown/HTML evidence report.
  - CSV curve archive.
  - Model limitations and fitting knobs.

## MVP Scope

The smallest useful open-source toolkit would support:

1. One device family: N-channel power MOSFET / SiC MOSFET.
2. Manual or vector-assisted curve extraction.
3. JSON/YAML parameter schema.
4. Common ABM + LTspice + ngspice model emitters.
5. LTspice batch validation if available.
6. A report that separates datasheet values from fitted parameters.

The current S4661 workspace already has:

- `s4661_params.json`: seed schema.
- `tools/extract_s4661_fig19_capacitance.py`: vector extraction prototype.
- `tools/mosfet_model_packager.py`: model emitter prototype.
- LTspice smoke and double-pulse validation logs.

## Recommendation

Build it ourselves, but do not try to solve fully automatic PDF understanding first. Start with a semi-automatic, traceable engineering tool:

- automatic when PDF vector paths are clean,
- manual CSV import when plots are raster or messy,
- strict provenance for every number,
- simulator-specific emitters,
- automatic validation decks.

This is likely more reliable for research and teaching than a black-box "AI extracts everything" tool.

## Physical / Compact SPICE Model Support

SPICE "physical model" usually means a compact device model, not a full TCAD finite-element semiconductor simulation.

### What can be supported

- LTspice has standard MOSFET models and a proprietary intrinsic `VDMOS` power MOSFET model. Its local help says VDMOS directly encapsulates the charge behavior of a vertical double-diffused MOS transistor and was introduced for compute speed, convergence reliability, and simpler power MOSFET models.
- ngspice supports a `VDMOS` power MOSFET model. Its manual describes it as a relatively simple 3-terminal power MOS model based on MOS1 current equations, with constant `Cgs`, nonlinear `Cgd` via `Cgdmax/Cgdmin/A`, diode `Cjo`, leakage/breakdown, subthreshold, and quasi-saturation terms.
- ngspice also supports many IC-oriented compact MOS models: BSIM3, BSIM4, BSIMSOI, HiSIM2, HiSIM_HV, and via OSDI/OpenVAF can load Verilog-A compact models.

### Practical limitation

Datasheets usually provide enough information to seed VDMOS-like power MOS parameters:

- `Vto`
- `Kp`
- `Rd/Rs/Ron`
- `Cgdmax/Cgdmin/Cgs/Cjo`
- body diode `Is/Rs/BV/TT`
- optional quasi-saturation and subthreshold starter terms

Datasheets usually do not provide enough process/device-internal information to extract a full high-order BSIM/HiSIM model with confidence. For that, measured wafer/device characterization or vendor model parameters are normally required.

### Speed comparison

Typical speed ranking for switching transient studies:

1. Ideal switch or loss-table system model: fastest, least waveform detail.
2. Built-in VDMOS compact model: usually fast and robust because it is implemented inside the simulator in compiled code and has smoother built-in charge equations.
3. Simple ABM behavioral subcircuit: often acceptable, but can slow down if it uses many B sources, lookup tables, hard limiters, or non-charge-conserving capacitances.
4. Detailed vendor subcircuit/electrothermal model: more accurate for switching and temperature, often slower.
5. High-order compact models such as BSIM/HiSIM/Verilog-A with many effects: can be robust, but not necessarily faster than a simple behavior model; speed depends strongly on model complexity, simulator implementation, and parameter smoothness.

For this project, the best engineering route is to support both:

- `emit vdmos`: fast approximate compact model for LTspice/ngspice, good for early power-stage sweeps.
- `emit abm`: flexible datasheet-driven behavior model for fitting `Coss/Crss/Qg`, diode recovery, and parasitics.
- later `emit verilog-a`: open compact-model backend through OpenVAF/ngspice when we want a cleaner compiled model.
