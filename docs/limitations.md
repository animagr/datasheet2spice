# Limitations

`datasheet2spice` v1.0 is a semi-automatic model-starter toolkit, not a vendor
model generator.

- Generated models are not vendor-qualified or safety-qualified.
- Datasheet paths stored by `init` are provenance records. The browser
  workbench can upload and heuristically parse PDFs, but arbitrary datasheets
  still require human review.
- CSV curve import remains the most reliable path for `Ciss/Coss/Crss`; PDF
  text/vector extraction is experimental and layout dependent.
- Automatic curve digitization currently works on vector PDF curves. Raster-only
  plots and scanned datasheets still need manual CSV import.
- The model quality score is a triage signal based on extracted data
  consistency and simple fitting checks; final accuracy still requires SPICE
  smoke tests and comparison with datasheet or lab waveforms.
- The ABM capacitance implementation is a starter table model. Higher accuracy
  and faster convergence usually need smoothed charge functions fitted to
  `C(V)`, `Qg`, `Eoss`, and switching waveforms.
- `VDMOS` is a compact-model convenience available in LTspice/ngspice-like
  simulators; it is not universal SPICE syntax.
- The `common` ABM dialect is a best-effort netlist style, not a guarantee that
  every SPICE engine accepts the same behavioral-source functions.
- Temperature and self-heating are represented only through starter parameter
  tables. Full electrothermal behavior is future work.
- Package and PCB parasitics dominate fast switching waveforms; generated decks
  use starter values that must be replaced with the real test setup.
- Datasheet-derived JSON, curves, and generated `.lib` files may be subject to
  the datasheet vendor's terms. Decide separately whether your extracted data
  may be redistributed.
