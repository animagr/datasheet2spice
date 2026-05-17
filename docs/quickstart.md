# Quick Start

## Install From Source

```powershell
git clone <your-repo-url> datasheet2spice
cd datasheet2spice
python -m pip install -e .
```

The core package has no mandatory runtime dependencies and requires Python 3.10+.

## Ten-Minute End-To-End Path

Create a project, import a digitized capacitance curve, validate it, generate
both built-in model families, and render a report:

```powershell
datasheet2spice init MY_MOSFET path\to\datasheet.pdf --vendor VendorName --out my_mosfet.device.json
datasheet2spice import-capacitance-csv my_mosfet.device.json examples\demo_sic_mosfet\capacitance.csv
datasheet2spice validate my_mosfet.device.json
datasheet2spice emit my_mosfet.device.json --out build/my_mosfet --all --dialect all
datasheet2spice report my_mosfet.device.json --out build/my_mosfet/report.md
```

The CSV import only fills `dynamic.capacitance`; you still need to replace the
static ratings, `RDS(on)`, `VGS(th)`, `gfs`, gate resistance, body diode, and
parasitic values with real datasheet or lab-fitted values.

## Generate Demo Models

```powershell
datasheet2spice emit examples/demo_sic_mosfet/device.json --out build/demo --all --dialect all
```

Generated files include:

- `*_vdmos_*.lib`
- `*_abm_*.lib`
- `*_double_pulse_*.cir`

`--dialect all` emits common SPICE, LTspice, ngspice, PSpice, HSPICE, Xyce,
and experimental QSPICE variants. Native VDMOS cards are generated for LTspice
and ngspice; other VDMOS dialects use a portable MOS fallback subcircuit. See
[SPICE Dialects](spice_dialects.md).

## Validate And Report

```powershell
datasheet2spice validate examples/demo_sic_mosfet/device.json
datasheet2spice report examples/demo_sic_mosfet/device.json --out build/demo/report.md
```

## Start A New Device

```powershell
datasheet2spice init MY_MOSFET path\to\datasheet.pdf --vendor VendorName --out my_mosfet.device.json
```

Then fill the JSON with datasheet values. Curves can be added manually or imported from digitizer CSV files.

Minimum useful fields for the built-in emitters:

- `ratings.vdss_v`, `ratings.vgs_on_v`, `ratings.vgs_off_v`
- `static.vgs_th_v`, keyed by temperature in Celsius
- `static.rds_on_mohm`, keyed by temperature in Celsius
- `static.gfs_s`, `static.rg_int_ohm`
- `dynamic.capacitance.vds_v`, `ciss_pf`, `coss_pf`, `crss_pf`
- `dynamic.gate_charge.qg_nc`, `qgs_nc`, `qgd_nc`
- `dynamic.channel_fit.idsat_reference_a`, `vgs_reference_v`
- `dynamic.body_diode.vsd_25c_typ_v`, `trr_ns`, `qrr_nc`, `irrm_a`
- `parasitics.ld_nh`, `ls_nh`, `lg_nh`, `rg_ext_ohm`

Use [../examples/minimal_device/device.json](../examples/minimal_device/device.json) as a copyable template.

## Import Digitized Capacitance Curves

Export a CSV from WebPlotDigitizer, StarryDigitizer, or a spreadsheet with these columns:

```csv
vds_v,ciss_pf,coss_pf,crss_pf
0,1000,900,300
100,820,240,35
```

Import it into the project:

```powershell
datasheet2spice import-capacitance-csv my_mosfet.device.json caps.csv
```

Use `--out reviewed.device.json` if you want to keep the original project unchanged.

## Run LTspice Batch Validation

```powershell
datasheet2spice run-ltspice build/demo/DEMO_SIC_1200_double_pulse_abm_ltspice.cir --ltspice "C:\Users\you\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
```

LTspice is proprietary and is not bundled.

Validation levels:

- `validate`: schema and numeric sanity checks before model emission.
- netlist smoke: generated decks parse and run without fatal simulator errors.
- transient benchmark: generated double-pulse waveforms are compared to datasheet test conditions.
- lab fit: parameters are tuned against measured `VDS/VGS/ID` waveforms and parasitic layout data.
