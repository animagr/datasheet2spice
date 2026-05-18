---
layout: default
---

# Interface Contracts

`datasheet2spice` uses two stable JSON-first contracts:

- `datasheet2spice-api-v1`: operations exposed by browser, local, or future
  remote backends.
- `datasheet2spice-module-v1`: manifests exposed by extractors, model emitters,
  fitters, validators, component profiles, backend adapters, and tool panels.

The goal is to let new modules join through registration instead of changing
the workbench control flow.

<img src="assets/diagrams/runtime-split.svg" alt="Shared API contract and plugin surfaces">

## Module Manifest

Every module should expose a small manifest:

```json
{
  "contract": "datasheet2spice-module-v1",
  "id": "my-company.power-diode-extractor",
  "kind": "extractor",
  "label": "Power Diode Extractor",
  "version": "0.1.0",
  "description": "Extracts diode ratings and recovery parameters.",
  "component_profiles": ["diode.power"],
  "runtime_modes": ["browser-pages", "local-python"],
  "capabilities": ["extract_pdf_text", "extract_project_from_text"],
  "dependencies": []
}
```

Module ids should use lowercase letters, numbers, `.`, `_`, and `-`.

## Module Kinds

- `component-profile`: declares a device family and its expected fields.
- `extractor`: turns PDF text, tables, images, curves, or lab files into project
  data and evidence.
- `model-emitter`: generates SPICE, Verilog-A, reports, or bundle files.
- `fitter`: turns reviewed values, curves, or waveforms into model parameters.
- `validator`: checks schema, units, physical consistency, and model readiness.
- `tool-panel`: adds a frontend tool such as gate-drive, thermal RC, or
  double-pulse helpers.
- `backend-adapter`: connects the frontend to browser, local, or remote
  execution.

## Backend Operations

The shared API contract includes these operations:

- `capabilities`
- `extractPdf`
- `fitModel`
- `emitModelBundle`
- `digitizeCurve`
- `runValidation`

Not every runtime has to implement every operation. GitHub Pages mode should
provide lightweight extraction and model export. The local Python backend should
provide high-fidelity extraction, evidence, fitting, and simulator adapters.

`extractPdf` responses return a selected `project`. When an extractor detects a
multi-part datasheet, it should also return:

- `series`: `parts`, `default_part`, `selected_part`, `has_default`, and a
  common/varying field summary.
- `variant_projects`: one complete `DeviceProject` per detected part.
- `series_variants`: optional per-part findings and warnings for richer review
  UIs.

If `has_default` is false, frontends should require the user to choose a part
before generating a single model. They may also offer all-variant bundle
generation by passing `projects` to `emitModelBundle`.

## Python Extension Example

```python
from datasheet2spice.contracts import module_manifest
from datasheet2spice.plugins import extractor

@extractor("my-company.power-diode-extractor")
class PowerDiodeExtractor:
    label = "Power Diode Extractor"
    component_profiles = ("diode.power",)
    runtime_modes = ("local-python",)

    def manifest(self):
        return module_manifest(
            "my-company.power-diode-extractor",
            "extractor",
            self.label,
            component_profiles=self.component_profiles,
            runtime_modes=self.runtime_modes,
            capabilities=("extract_pdf", "extract_tables"),
        )

    def extract(self, source, **options):
        ...
```

## Browser Extension Example

```js
export const MY_TOOL_MODULE = {
  id: "my-company.gate-resistor-tool",
  kind: "tool-panel",
  label: "Gate Resistor Tool",
  version: "0.1.0",
  component_profiles: ["mosfet.power"],
  runtime_modes: ["browser-pages"],
  capabilities: ["render_tool_panel"],
  render(container, project) {
    // Create the tool UI here.
  }
};
```

Browser modules are registered with `WorkbenchModuleRegistry` from
`web/assets/module_contracts.js`.

## Current Built-In Modules

- `mosfet.power`: component profile.
- `diode.power`: component profile.
- `abm-basic`: ABM starter model emitter.
- `diode-basic`: portable diode compact model emitter.
- `vdmos-static-fast`: VDMOS starter model emitter.
- `capacitance-csv`: CSV capacitance curve extractor.
- `schema`: project schema validator.
- `browser-pdf-text-extractor`: hosted browser PDF text extractor.
- `browser-spice-starter-emitter`: hosted browser SPICE starter emitter.
