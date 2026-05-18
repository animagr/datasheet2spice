---
layout: default
---

# Plugin Interfaces

The plugin registry supports component profiles, emitters, extractors, fitters,
tool panels, and validators.

Each registered plugin is also represented by a `datasheet2spice-module-v1`
manifest. See [Interface Contracts](interface_contracts.md) for the manifest
shape and backend operation contract.

## Component Profiles

Component profiles define what a device family expects from extraction, fitting,
and model generation.

The first built-in profile is:

- `mosfet.power`

Future profiles should add their own expected fields, recommended model
families, validators, and review tools without changing the core schema.

## Emitters

```python
from datasheet2spice.plugins import emitter

@emitter("my-model")
class MyEmitter:
    def emit(self, project, dialect="common"):
        return {"model.lib": "* spice text\n"}
```

Built-in emitters:

- `vdmos-static-fast`
- `abm-basic`

## Extractors

Built-in extractors:

- `capacitance-csv`

## Validators

Built-in validators:

- `schema`

Optional extractors can live under `datasheet2spice.extractors` or in external packages.

## Fitters and Tool Panels

Fitters are intended for parameter extraction from curves, measured waveforms,
or reviewed project data. Tool panels are intended for frontend extensions such
as gate-resistor calculators, thermal RC fitters, double-pulse setup helpers,
and curve review utilities.

These interfaces are registered today so downstream packages can target them,
even though the built-in v1 package only ships MOSFET starter fitting helpers.

## Third-Party Package Loading

External packages can expose a plugin entry point in `pyproject.toml`:

```toml
[project.entry-points."datasheet2spice.plugins"]
my_vendor_models = "my_vendor_models"
```

The target can be a module imported for decorator side effects, or a callable
that accepts the global registry:

```python
def register(registry):
    registry.extractors["my-extractor"] = MyExtractor()
```

Entry point plugins are disabled by default because loading one executes
arbitrary installed Python. For trusted local extensions only, call
`load_plugins(include_entrypoints=True)` from Python or set
`DATASHEET2SPICE_ENABLE_ENTRYPOINT_PLUGINS=1` before running CLI commands.

## Optional PDF Extraction

`datasheet2spice.extractors.pymupdf_vector` demonstrates a PyMuPDF-based vector extractor. It imports PyMuPDF only inside the function so users who do not want AGPL/commercial PyMuPDF do not need to install it.

## CSV Curve Import

`datasheet2spice.extractors.csv_curves.read_capacitance_csv` supports CSV exports from WebPlotDigitizer, StarryDigitizer, or spreadsheets, with columns:

```text
vds_v,ciss_pf,coss_pf,crss_pf
```
