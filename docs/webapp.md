# Browser Workbench

The local browser workbench lets a user upload a MOSFET datasheet PDF, review
automatically extracted parameters, choose model families, and generate a ZIP
model bundle.

Start it from the repository:

```powershell
python -m pip install -e .[pdf]
datasheet2spice serve --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## Workflow

1. Upload a PDF datasheet.
2. Review the extracted fields, confidence scores, warnings, and source snippets.
3. Edit the project JSON if a value is wrong or missing.
4. Select `ABM 行为模型`, `VDMOS 紧凑模型`, and the target SPICE dialect.
5. Generate and download the ZIP model bundle.

Generated files are written under `build/webapp/<session>/generated/`.

## Extraction Scope

The v1.0 workbench uses PyMuPDF text extraction plus datasheet heuristics. It is
good enough to create a reviewable starter model from many tabular MOSFET
datasheets, but it is not a full semantic datasheet parser.

The extractor currently targets common fields:

- `VDSS`, continuous `ID`, `VGS_on`, `VGS_off`
- `VGS(th)`, `RDS(on)`, `gfs`, internal `RG`
- `Ciss`, `Coss`, `Crss`
- `Qg`, `Qgs`, `Qgd`
- body-diode `VSD`, `trr`, `Qrr`, `Irrm`

If only one capacitance point is found, the workbench creates a conservative
starter `C(V)` curve so the built-in emitters can run. Replace it with a
digitized curve for serious transient fitting.
