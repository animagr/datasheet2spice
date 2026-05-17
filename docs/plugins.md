---
layout: default
---

# Plugin Interfaces

The built-in plugin registry supports emitters, extractors, and validators.

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

Built-in extractors:

- `capacitance-csv`

Built-in validators:

- `schema`

Optional extractors can live under `datasheet2spice.extractors` or in external packages.

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

The CLI loads these entry points before `emit` and `plugins`.

## Optional PDF Extraction

`datasheet2spice.extractors.pymupdf_vector` demonstrates a PyMuPDF-based vector extractor. It imports PyMuPDF only inside the function so users who do not want AGPL/commercial PyMuPDF do not need to install it.

## CSV Curve Import

`datasheet2spice.extractors.csv_curves.read_capacitance_csv` supports CSV exports from WebPlotDigitizer, StarryDigitizer, or spreadsheets, with columns:

```text
vds_v,ciss_pf,coss_pf,crss_pf
```
