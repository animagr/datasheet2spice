# datasheet2spice web frontend

This directory is the source area for the lightweight browser workbench.

The GitHub Pages deployment still serves files from `docs/`, so the current
workflow keeps deployable copies in sync:

- `web/workbench_app.html` -> `docs/workbench_app.html`
- `web/assets/*.js` -> `docs/assets/*.js`

Run this before publishing frontend changes:

```powershell
python tools/sync_web_frontend.py
```

## Runtime Adapters

The workbench targets `datasheet2spice-api-v1` through frontend adapters:

- `browser-pages`: the default GitHub Pages mode, fully static and no-install.
- `local-python`: optional local backend mode for high-fidelity extraction,
  evidence rendering, fitting, and simulator checks.

The hosted page should remain useful in `browser-pages` mode. Features that
require local files, OCR engines, or simulator execution should be routed
through `local-python` or a future remote backend instead of being hardwired
into the static page.

Modules should expose `datasheet2spice-module-v1` manifests and register with
`WorkbenchModuleRegistry` from `assets/module_contracts.js`.

## Module Layout

- `workbench_app.js`: DOM wiring and user workflow.
- `workbench_runtime.js`: backend mode and adapter contract.
- `module_contracts.js`: browser module manifest validation and registry.
- `pdf_extractors.js`: browser PDF text extraction and starter project heuristics.
- `model_emitters.js`: browser-side starter SPICE bundle generation.
