---
layout: default
---

# Device Schema

The project file is JSON. `DeviceProject` remains the backward-compatible class
name. `ComponentProject` is an alias used by the broader roadmap, where the same
envelope can represent MOSFETs, diodes, IGBTs, BJTs, op amps, and future
component families.

Top-level fields:

- `schema_version`
- `component`
- `device`
- `ratings`
- `static`
- `dynamic`
- `parasitics`
- `models`
- `provenance`

The schema is intentionally permissive in v1.0 so new devices can be supported
without migrations. Component profiles define stricter family-specific
expectations.

Datasheets that contain several related orderable parts can expose
`device.series_parts` in each generated project. Extraction APIs also return a
separate `series` object and `variant_projects` list so the UI can require an
explicit user choice when the uploaded filename does not identify a default
part.

## Component Envelope

New projects include:

```json
{
  "component": {
    "family": "mosfet",
    "profile": "mosfet.power"
  }
}
```

The `component.profile` value selects the extraction, fitting, validation, and
model-generation expectations for that device family. Older project files
without this envelope still load.

## Minimum Built-In Emitter Inputs

The built-in `vdmos-static-fast` and `abm-basic` MOSFET emitters can produce
starter models when these fields are present:

- `ratings.vdss_v`: drain-source voltage rating in volts.
- `ratings.vgs_on_v`, `ratings.vgs_off_v`: gate drive levels in volts.
- `static.vgs_th_v`: temperature-keyed threshold voltage map, for example `{ "25": 3.8 }`.
- `static.rds_on_mohm`: temperature-keyed on-resistance map in milliohms.
- `static.gfs_s`: forward transconductance in siemens.
- `static.rg_int_ohm`: internal gate resistance in ohms.
- `dynamic.capacitance`: `vds_v`, `ciss_pf`, `coss_pf`, `crss_pf` arrays.
- `dynamic.channel_fit.idsat_reference_a` and `vgs_reference_v`: one current point for the smooth ABM channel starter.
- `dynamic.body_diode`: `vsd_25c_typ_v`, `trr_ns`, `qrr_nc`, `irrm_a`.
- `parasitics`: package and starter testbench values `ld_nh`, `ls_nh`, `lg_nh`, `rg_ext_ohm`.

The values may be datasheet typical values, conservative assumptions, or lab
fits, but each source should be recorded in `provenance`.

The built-in `diode-basic` and `diode-abm-dynamic` emitters use the
`diode.power` profile and these fields when available:

- `ratings.vrrm_v`: repetitive peak reverse-voltage rating in volts.
- `ratings.if_av_a`, `ratings.ifsm_a`: average and surge forward current.
- `static.forward_voltage`: `vf_v` and reference `if_a`.
- `static.leakage.ir_ua`: reverse leakage current.
- `dynamic.junction_capacitance.cj0_pf`: starter junction capacitance.
- `dynamic.reverse_recovery`: `trr_ns`, `qrr_nc`, and optional `irrm_a`.
- `parasitics`: `la_nh`, `lk_nh`, `ra_ohm`, and `rk_ohm`.

## Provenance

Every value extracted from a datasheet should eventually record:

- source file
- page
- table or figure number
- extraction method
- confidence
- whether it is datasheet, fitted, lab-fitted, or assumed

The built-in `import-capacitance-csv` command appends a provenance item with
`kind: digitized_capacitance_csv` so generated models can be traced back to the
curve source. The WebPlotDigitizer-native `import-wpd-capacitance-csv` command
uses `kind: webplotdigitizer_capacitance_csv`.

## Capacitance Curves

`dynamic.capacitance` uses this v1.0 shape:

```json
{
  "vds_v": [0.0, 100.0],
  "ciss_pf": [1000.0, 820.0],
  "coss_pf": [900.0, 240.0],
  "crss_pf": [300.0, 35.0]
}
```

Values are stored in volts and picofarads because that matches most datasheet
plots and SPICE starter tables.

## Example

See [../examples/demo_sic_mosfet/device.json](../examples/demo_sic_mosfet/device.json).
