# Contributing

Thanks for helping build `datasheet2spice`. The project needs power electronics
users, simulator users, PDF/OCR people, frontend contributors, and anyone who
can bring real datasheet cases.

## Good First Contributions

Useful small contributions include:

- add a public datasheet case to `validation/public_datasheet_cases.json`,
- add a golden case under `validation/golden/`,
- improve a README or tutorial for your simulator,
- add one extraction fixture for a table layout that currently fails,
- run `benchmark-model` on a device and attach the report to an issue,
- improve error messages or review UI copy.

## Development Setup

```powershell
python -m pip install -e .[pdf]
$env:PYTHONPATH="$PWD\src"
python -m unittest discover -s tests -v
```

Before pushing, run:

```powershell
python -m unittest discover -s tests -v
datasheet2spice score-case examples/demo_sic_diode/device.json validation/golden/demo_sic_diode.case.json
datasheet2spice benchmark-model examples/demo_sic_diode/device.json --out build/bench-diode --model diode-basic --model diode-abm-dynamic --dialect all
git diff --check
```

If you change frontend files under `web/`, also run:

```powershell
python tools/sync_web_frontend.py
```

## Contribution Rules

- Keep core runtime dependencies minimal.
- Put optional AGPL/GPL/proprietary integrations behind plugins.
- Do not commit confidential datasheets, vendor encrypted models, simulator raw
  files, or large generated bundles.
- Store third-party PDF/model URLs and expected values, not redistributed vendor
  files.
- Keep generated model claims modest and traceable.
- Add tests for new emitters, extractors, validators, and quality gates.

## New Datasheet Case Checklist

- Public source URL is included.
- Vendor and part numbers are clear.
- Component profile is set, such as `mosfet.power` or `diode.power`.
- Layout tags describe the challenge, such as `series-datasheet`,
  `scanned-pdf`, `capacitance-curve`, or `vendor-spice-model`.
- Expected fields include units and tolerances.
- Any vendor SPICE model license constraints are noted.

## New Emitter Checklist

- Registers through `datasheet2spice.plugins.emitter`.
- Supports at least one documented dialect.
- Emits deterministic text.
- Has tests and a benchmark path.
- Documents convergence and accuracy limitations.

## Pull Requests

Open a draft PR early if you want design feedback. A good PR description states:

- what changed,
- how it was tested,
- what model/extraction limitations remain,
- whether any generated evidence files are included.
