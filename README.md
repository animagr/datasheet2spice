# datasheet2spice

`datasheet2spice` is a traceable, semi-automatic toolkit for turning power MOSFET and SiC MOSFET datasheet information into SPICE model starters.

It is designed for engineering work where every number must be auditable. It does **not** claim that a generated model is a vendor-qualified model. Generated models are starting points for simulation and lab fitting.

## What It Does

- Stores extracted datasheet values in a structured JSON schema with provenance.
- Emits fast `VDMOS` compact model starters.
- Emits simple ABM behavioral model starters for common SPICE, LTspice, and ngspice styles.
- Generates double-pulse starter decks.
- Provides plugin interfaces and Python entry points for PDF extraction, curve import, emitters, and validators.
- Keeps AGPL/GPL tools optional instead of mandatory runtime dependencies.

## Quick Start

Python 3.10+ is required. From a fresh clone:

```powershell
python -m pip install -e .
```

Generate demo models:

```powershell
datasheet2spice emit examples/demo_sic_mosfet/device.json --out build/demo --all
```

Validate schema and print a short model report:

```powershell
datasheet2spice validate examples/demo_sic_mosfet/device.json
datasheet2spice report examples/demo_sic_mosfet/device.json
```

Run the local browser workbench for PDF upload and model generation:

```powershell
python -m pip install -e .[pdf]
datasheet2spice serve --host 127.0.0.1 --port 8765
```

Ten-minute path for a new device:

```powershell
datasheet2spice init MY_PART path\to\datasheet.pdf --vendor VendorName --out my_part.device.json
datasheet2spice import-capacitance-csv my_part.device.json examples\demo_sic_mosfet\capacitance.csv
datasheet2spice validate my_part.device.json
datasheet2spice emit my_part.device.json --out build/my_part --all --dialect all
datasheet2spice report my_part.device.json --out build/my_part/report.md
```

Import capacitance curves digitized from a datasheet plot:

```powershell
datasheet2spice import-capacitance-csv my_part.device.json caps.csv
```

The CSV columns are `vds_v,ciss_pf,coss_pf,crss_pf`.

Run tests:

```powershell
python -m unittest discover -s tests -v
```

Create a new project file:

```powershell
datasheet2spice init MY_PART path\to\datasheet.pdf --out my_part.device.json
```

In v1.0 the datasheet path is recorded for provenance; automatic PDF extraction
is experimental and exposed through optional plugins. The reliable workflow is:
extract table values, digitize curves to CSV, validate, emit, then fit against
datasheet or lab waveforms.

## Model Families

`VDMOS static-fast`

- Fast compact model baseline.
- Good for early power-stage sweeps.
- Datasheet-driven starter parameters: `Vto`, `Kp`, `Rd/Rs`, `Rg`, `Cgs`, `Cgdmin/max`, `Cjo`, diode terms.

`ABM dynamic-basic`

- Flexible behavioral starter.
- Uses smooth `Idsat(Vgs)` plus `RDS(on)` and nonlinear capacitance tables.
- Supports common ABM, LTspice, and ngspice emitter dialects.

## License

The core package is Apache-2.0. Optional integrations may have stronger licenses. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Documentation

- [Quick Start](docs/quickstart.md)
- [Architecture](docs/architecture.md)
- [Schema](docs/schema.md)
- [Plugins](docs/plugins.md)
- [Browser Workbench](docs/webapp.md)
- [Modeling Notes](docs/modeling.md)
- [Limitations](docs/limitations.md)
- [License Strategy](docs/license_strategy.md)
- [Roadmap](docs/roadmap.md)

## Important Caveats

- Do not redistribute confidential datasheets without permission.
- Do not treat generated models as safety-qualified vendor models.
- Always validate switching behavior against datasheet test conditions or measured double-pulse waveforms.
- High-order BSIM/HiSIM extraction generally requires process/device characterization data beyond ordinary datasheets.
