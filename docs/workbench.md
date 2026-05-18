---
layout: default
title: Web Workbench
---

# Web Workbench

This browser-only workbench runs from GitHub Pages. It can extract starter
MOSFET or diode parameters from PDF text, edit the project JSON, and generate
starter SPICE files without installing Python.

The hosted page is useful for quick reviews and sharing. The local Python
workbench remains the higher-fidelity path for screenshot evidence, calibrated
raster plot digitization, and server-side PyMuPDF extraction.

<p>
  <a class="button" href="workbench_app.html">Open the Web Workbench</a>
</p>

## Current Browser-Only Scope

- PDF text extraction through PDF.js.
- Heuristic MOSFET and diode parameter extraction.
- Diode series-part detection, explicit part selection, and all-variant ZIP export.
- Editable `DeviceProject` JSON.
- ABM, VDMOS, diode compact, and diode behavioral starter netlist generation.
- Dialects: common, LTspice, ngspice, PSpice, HSPICE, Xyce, and experimental QSPICE.
- ZIP download through JSZip.

## Planned WASM Path

GitHub Pages can serve static WebAssembly artifacts. That means the heavier
parts of the local workbench can later move into a Rust/WASM module:

- robust PDF text/table extraction,
- raster image preprocessing,
- curve tracing,
- fitting and quality scoring,
- deterministic netlist generation shared by CLI and browser.

The hosted workbench should remain a lightweight public entry point. Features
that need local files, simulator execution, large OCR models, or long-running
jobs should stay behind the local Python backend or a future optional remote
API. See [Deployment Modes](deployment_modes.md).

Frontend source files live in `web/`; GitHub Pages copies are kept in `docs/`.
Run `python tools/sync_web_frontend.py` after changing the source frontend.
The browser code is split into `workbench_app.js`, `workbench_runtime.js`,
`pdf_extractors.js`, and `model_emitters.js` so the hosted demo can evolve
without turning the HTML page back into a monolith.
