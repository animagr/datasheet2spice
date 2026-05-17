# Third-Party License Notes

This project keeps the core runtime dependency-free and Apache-2.0 licensed.
Some optional integrations are intentionally isolated because their licenses may
impose stronger obligations.

This is engineering guidance, not legal advice.

## Core Package

- Mandatory runtime dependencies: none.
- License: Apache-2.0.

## Optional / External Tools

| Tool | Typical Use | License Note | Bundled? |
|---|---|---|---|
| PyMuPDF / MuPDF | PDF vector/text extraction plugin | AGPL-3.0 or commercial license from Artifex | No |
| WebPlotDigitizer | Manual plot digitization, CSV export | AGPL-3.0 frontend; cloud AI Assist is not open source | No |
| StarryDigitizer | Browser-based graph digitization | Check upstream license before bundling | No |
| PySpice | Python ngspice/Xyce interface | GPL-3.0 | No |
| spicelib / PyLTSpice | SPICE automation and waveform reading | GPL-3.0 | No |
| LTspice | Optional local simulator | Proprietary Analog Devices software | No |
| ngspice | Optional local simulator | External executable; check installed distribution license | No |
| OpenVAF | Future Verilog-A backend | External compiler; check upstream license | No |

## Design Decision

The core project does not import PyMuPDF, PySpice, spicelib, WebPlotDigitizer,
or LTspice at import time. Integrations should either:

- call external executables through subprocess,
- import optional packages only inside plugin functions,
- or accept CSV/JSON exports produced by third-party tools.

This allows users to choose the optional workflow whose license terms match
their project.
