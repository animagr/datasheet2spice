# Demo SiC MOSFET Example

This example is synthetic. It is intended for tests and tutorials, not for real design.

Import the example capacitance CSV into a fresh project:

```powershell
datasheet2spice init DEMO_IMPORT synthetic-demo --vendor DemoVendor --out build/demo_import.device.json
datasheet2spice import-capacitance-csv build/demo_import.device.json examples/demo_sic_mosfet/capacitance.csv
```

Generate all starter models:

```powershell
datasheet2spice emit examples/demo_sic_mosfet/device.json --out build/demo --all --dialect all
```

Render a report:

```powershell
datasheet2spice report examples/demo_sic_mosfet/device.json --out build/demo/report.md
```
