# Minimal Device Template

This template shows the smallest project shape that the built-in VDMOS and ABM
emitters need.

```powershell
datasheet2spice validate examples/minimal_device/device.json
datasheet2spice emit examples/minimal_device/device.json --out build/minimal --all --dialect all
```

All values are placeholders. Replace them with datasheet or lab-fitted values
before using the generated models for engineering decisions.
