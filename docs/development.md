---
layout: default
---

# Development Workflow

This project keeps source, deployable web files, examples, and local generated
artifacts separate so a datasheet review session does not pollute commits.

## Repository Layout

- `src/datasheet2spice/`: Python package, extractors, fitters, emitters,
  validators, service layer, and local HTTP workbench.
- `web/`: source for the static browser workbench.
- `docs/`: GitHub Pages documentation and deployable copies of the web
  workbench.
- `examples/`: small public JSON examples and plugin examples.
- `tests/`: unit and smoke tests.
- `tools/`: project maintenance and one-off extraction helpers.
- `tmp/`: ignored local datasheets, upload sessions, and generated review
  output.
- `build/`: ignored generated models, reports, screenshots, and package builds.

## Frontend Sync

Edit the browser workbench under `web/`. After every frontend change, run:

```powershell
python tools/sync_web_frontend.py
```

That copies the deployable files into `docs/` for GitHub Pages. CI checks that
the copies are synchronized.

## Local Datasheets

Vendor datasheets and rendered evidence images are ignored by default. Keep
local PDFs under:

```text
tmp/local_datasheets/
```

For example, optional S4661 smoke tests look for:

```text
tmp/local_datasheets/TK-S4661_Rev.T17.2.pdf
```

Generated model files, LTspice logs, raw files, and temporary review bundles
belong under `build/` or `tmp/`, not the repository root.

## Validation Before Publishing

Run these checks before pushing:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
datasheet2spice score-case examples/demo_sic_diode/device.json validation/golden/demo_sic_diode.case.json
datasheet2spice benchmark-model examples/demo_sic_diode/device.json --out build/bench-diode --model diode-basic --model diode-abm-dynamic --dialect all
git diff --check
python tools/sync_web_frontend.py
git diff --exit-code -- docs/workbench_app.html docs/assets/model_emitters.js docs/assets/module_contracts.js docs/assets/pdf_extractors.js docs/assets/workbench_app.js docs/assets/workbench_runtime.js
```

Also scan public documentation and UI copy for accidental placeholder text,
locale markers, or non-English copy before publishing. The public GitHub Pages
surface is kept in English.
