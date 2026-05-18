---
layout: default
---

# Deployment Modes

The project supports lightweight static browser files and a higher-fidelity
local backend. Both should use the same project JSON and model-generation
semantics.

## Static Browser Mode

Target: local/static files opened by a browser.

Use this mode for:

- local demos,
- manual project review,
- starter model generation,
- individual file downloads,
- future Rust/WASM fitting and curve helpers.

Expected limits:

- no direct LTspice/ngspice/Xyce execution,
- limited scanned-PDF OCR,
- limited long-running batch jobs,
- no server-side storage for user uploads.

## Local Python Backend

Target: the user's workstation.

Use this mode for:

- PyMuPDF text extraction,
- PDF evidence screenshots,
- table candidate recognition,
- vector capacitance curve digitization,
- calibrated raster curve digitization,
- fitting and quality scoring,
- optional simulator smoke tests.

The current local HTTP server is intentionally small and calls
`datasheet2spice.service` for backend work. A future FastAPI server can expose
the same service functions through a cleaner REST API without changing the
frontend contract.

## Frontend Contract

The web app should depend on a small set of backend operations:

```text
createProject
extractPdf
getEvidence
reviewFinding
digitizeCurve
fitModel
emitModelBundle
runValidation
```

Adapters can implement those operations through browser-only JavaScript/WASM or
the local Python backend.
The formal operation list is exported by `datasheet2spice.contracts.service_contract()`
and documented in [Interface Contracts](interface_contracts.md).

The lightweight frontend source lives under `web/`. `tools/sync_web_frontend.py`
copies the source frontend files into `docs/` so documentation and static files
stay synchronized.

The browser workbench frontend is split into small ES modules:

- `workbench_app.js` for DOM wiring,
- `workbench_runtime.js` for backend mode selection,
- `pdf_extractors.js` for extraction heuristics when a trusted local parser is supplied,
- `model_emitters.js` for static starter SPICE bundle generation.
