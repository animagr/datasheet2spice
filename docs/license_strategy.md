# License Strategy

The project core is Apache-2.0.

Reasons:

- permissive for academic and industrial use,
- explicit patent grant,
- compatible with many downstream uses,
- avoids forcing users into AGPL/GPL obligations for workflows that do not need AGPL/GPL tools.

## Optional Integrations

PyMuPDF/MuPDF is AGPL-3.0 or commercial. The PyMuPDF vector extractor is optional and not imported by the core package.

WebPlotDigitizer is not bundled. Users can export CSV and import the CSV.

PySpice and spicelib/PyLTSpice are not mandatory dependencies. The core validator can call simulator executables through subprocess instead.

## Datasheet Rights

Datasheets may be copyrighted or confidential. Do not include confidential datasheets in the public repository. Prefer synthetic examples or datasheets that explicitly allow redistribution.

Generated JSON, CSV, and SPICE files are normally authored by the user or their
organization, but they may contain facts, curves, or derived data copied from a
vendor datasheet. The project license does not grant permission to redistribute
that vendor-derived data. Keep public examples synthetic or explicitly
redistributable.

Installing `datasheet2spice[pdf]` may install PyMuPDF/MuPDF, which is AGPL-3.0
or commercially licensed. Users who need a purely permissive dependency stack
should avoid the optional PDF extra and use CSV import or external tools.
