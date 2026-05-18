---
layout: default
---

# Deployment Modes

The project supports a lightweight hosted workbench and a higher-fidelity local
backend. Both should use the same project JSON and model-generation semantics.

## Browser Pages Mode

Target: GitHub Pages.

Use this mode for:

- public demos,
- no-install PDF text extraction,
- manual project review,
- starter model generation,
- ZIP downloads,
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

## Future Remote API

Target: optional hosted service.

Use this mode later for:

- AI-assisted extraction,
- stronger OCR and layout understanding,
- batch processing,
- team model libraries,
- collaboration and review history.

This mode requires privacy, cost, and API-key design, so it should not block the
open-source local and GitHub Pages workflows.

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

Adapters can implement those operations through browser-only JavaScript/WASM,
the local Python backend, or a future remote API.
The formal operation list is exported by `datasheet2spice.contracts.service_contract()`
and documented in [Interface Contracts](interface_contracts.md).

The lightweight frontend source lives under `web/`. GitHub Pages still publishes
from `docs/`, so `tools/sync_web_frontend.py` copies the source frontend files
into the deployable docs tree and tests verify the copies stay identical.

The browser workbench frontend is split into small ES modules:

- `workbench_app.js` for DOM wiring,
- `workbench_runtime.js` for backend mode selection,
- `pdf_extractors.js` for browser PDF text heuristics,
- `model_emitters.js` for static starter SPICE bundle generation.
