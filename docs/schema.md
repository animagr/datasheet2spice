---
layout: default
---

# Device Schema

The project file is JSON.

Top-level fields:

- `schema_version`
- `device`
- `ratings`
- `static`
- `dynamic`
- `parasitics`
- `models`
- `provenance`

The schema is intentionally permissive in v1.0 so new devices can be supported without migrations.

## Minimum Built-In Emitter Inputs

The built-in `vdmos-static-fast` and `abm-basic` emitters can produce starter
models when these fields are present:

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
curve source.

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
