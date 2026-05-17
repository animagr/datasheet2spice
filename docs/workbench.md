---
layout: default
title: Web Workbench
---

# Web Workbench

This browser-only workbench runs from GitHub Pages. It can extract starter
MOSFET parameters from PDF text, edit the project JSON, and generate starter
SPICE files without installing Python.

The hosted page is useful for quick reviews and sharing. The local Python
workbench remains the higher-fidelity path for screenshot evidence, calibrated
raster plot digitization, and server-side PyMuPDF extraction.

<p>
  <a class="button" href="workbench_app.html">Open the Web Workbench</a>
</p>

## Current Browser-Only Scope

- PDF text extraction through PDF.js.
- Heuristic MOSFET parameter extraction.
- Editable `DeviceProject` JSON.
- ABM and VDMOS starter netlist generation.
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

