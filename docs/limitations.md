# Limitations

`datasheet2spice` v1.0 is a semi-automatic model-starter toolkit, not a vendor
model generator.

- Generated models are not vendor-qualified or safety-qualified.
- Datasheet paths stored by `init` are provenance records. The browser
  workbench can upload and heuristically parse PDFs, but arbitrary datasheets
  still require human review.
- CSV curve import remains the most reliable path for `Ciss/Coss/Crss`; PDF
  text/vector extraction is experimental and layout dependent.
- Automatic curve digitization works best on vector PDF curves. Raster-only
  plots and scanned datasheets can be digitized with the calibrated raster tool,
  but low-resolution scans, touching grid lines, and poor contrast still need
  human review.
- The model quality score is a triage signal based on extracted data
  consistency and simple fitting checks; final accuracy still requires SPICE
  smoke tests and comparison with datasheet or lab waveforms.
- The ABM capacitance implementation is a starter table model. Higher accuracy
  and faster convergence usually need smoothed charge functions fitted to
  `C(V)`, `Qg`, `Eoss`, and switching waveforms.
- Native `VDMOS` model cards are emitted only for LTspice and ngspice. Other
  dialects receive a portable MOS fallback subcircuit for the `vdmos-static-fast`
  family.
- The `common`, PSpice, HSPICE, Xyce, and QSPICE ABM dialects are best-effort
  starter netlists; each target simulator should still be smoke-tested.
- Temperature and self-heating are represented only through starter parameter
  tables. Full electrothermal behavior is future work.
- Package and PCB parasitics dominate fast switching waveforms; generated decks
  use starter values that must be replaced with the real test setup.
- Datasheet-derived JSON, curves, and generated `.lib` files may be subject to
  the datasheet vendor's terms. Decide separately whether your extracted data
  may be redistributed.
