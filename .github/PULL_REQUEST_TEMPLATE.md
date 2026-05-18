## Summary

- 

## Type

- [ ] Extractor / PDF parsing
- [ ] Model emitter / fitting
- [ ] Simulator benchmark / validation
- [ ] Browser workbench
- [ ] Documentation
- [ ] Tests / maintenance

## Validation

- [ ] `python -m unittest discover -s tests -v`
- [ ] `datasheet2spice score-case examples/demo_sic_diode/device.json validation/golden/demo_sic_diode.case.json`
- [ ] `datasheet2spice benchmark-model examples/demo_sic_diode/device.json --out build/bench-diode --model diode-basic --model diode-abm-dynamic --dialect all`
- [ ] Frontend copied with `python tools/sync_web_frontend.py` if `web/` changed

## Model or Extraction Limitations

Describe remaining assumptions, unsupported datasheet layouts, simulator dialect
limitations, or accuracy/convergence risks.

## Data and Licensing

- [ ] No confidential datasheets were committed.
- [ ] No restricted vendor model files were committed.
- [ ] Public datasheet/model links are documented when relevant.

