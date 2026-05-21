# MOSFET Switching Benchmark Evidence

## Question

Can generated MOSFET starter models be checked locally for the two failure modes
reported by early users: the device does not turn on under gate drive, or it
turns off with unrealistic ringing and unstable waveforms?

## Hypothesis

A generated double-pulse LTspice deck can be instrumented with `.meas` metrics
that catch first-order model failures before a human spends time inspecting raw
waveforms:

- gate drive reaches the intended on and off levels,
- load current builds during the on pulse,
- drain voltage pulls low in the on interval,
- turn-off drain overshoot stays below a conservative bus/device limit,
- turn-off drain peak-to-peak ringing stays below a review/fail threshold,
- simulator return code, fatal markers, warnings, and elapsed time remain
  traceable.

## Implementation

The `benchmark-model` command now accepts `--measure-switching`. For LTspice
MOSFET double-pulse decks, the benchmark inserts datasheet2spice-owned `.meas`
statements before `.end`, parses only `d2s_` measurement names from the LTspice
log, and writes the result into `benchmark_report.json` and
`benchmark_report.md`.

Command used locally:

```powershell
$env:PYTHONPATH='src'
python -m datasheet2spice benchmark-model examples\demo_sic_mosfet\device.json `
  --out build\mosfet-switching-benchmark `
  --model abm-basic `
  --model vdmos-static-fast `
  --dialect ltspice `
  --measure-switching `
  --run-ltspice `
  --ltspice "C:\Users\lsqba\AppData\Local\Programs\ADI\LTspice\LTspice.exe" `
  --timeout 120
```

## Local Result

Environment:

- LTspice executable: `C:\Users\lsqba\AppData\Local\Programs\ADI\LTspice\LTspice.exe`
- Project: `examples/demo_sic_mosfet/device.json`
- Output: `build/mosfet-switching-benchmark/benchmark_report.json`

Result:

| Model | Runtime | Warnings | Switching Status | Key Metrics |
| --- | ---: | ---: | --- | --- |
| `abm-basic` | 1.0909 s | 0 | pass | `Vg,on avg` 18.000 V, `Iload,on avg` 39.551 A, `Vds,on avg` 0.565 V, `Vds,off max` 802.846 V |
| `vdmos-static-fast` | 1.0127 s | 0 | pass | `Vg,on avg` 18.001 V, `Iload,on avg` 39.572 A, `Vds,on avg` 0.663 V, `Vds,off max` 802.848 V |

The synthetic demo case therefore does not reproduce the reported failure. That
is useful: the next debugging step is to run the same benchmark on the specific
real datasheet extraction, then compare against a same-vendor `.lib` reference
under the same external circuit.

## Browser Pages Emitter Check

A later check found that the GitHub Pages/browser ABM emitter had drifted from
the Python backend. It used a fixed-capacitance starter and a hard
`max(Vgs-Vth,0)^2` channel expression, while the Python backend used
`dynamic.channel_fit`, a smoothed overdrive function, and full `Ciss/Coss/Crss`
tables.

Before the fix, the browser ABM demo passed coarse first-pulse averages but
failed a second-pulse re-on check:

| Source | `Vds` below 100 V on second pulse | `d2s_vds_reon_max` |
| --- | ---: | ---: |
| Python ABM | 25.1618 us | about 2.0 V |
| Browser ABM before fix | 25.3286 us | about 802 V |

After aligning the browser emitter with the Python ABM semantics, the browser
ABM benchmark matched the Python backend:

| Source | `d2s_vg_on_avg` | `d2s_il_on_avg` | `d2s_vds_on_avg` | `d2s_vds_reon_max` | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| Browser ABM after fix | 18.000 V | 39.551 A | 0.565 V | 2.034 V | pass |
| Browser VDMOS after fix | 18.001 V | 39.572 A | 0.663 V | 1.332 V | pass |

The quality gate now treats an excessive second-pulse re-on drain voltage as a
hard failure, so this browser/backend drift should be caught automatically in
future local LTspice checks.

## Limitations

This benchmark is a gate, not a full accuracy proof. It does not yet compare raw
waveforms against a vendor `.lib` or measured double-pulse data. It catches
obvious opening, convergence, overshoot, and ringing failures so model changes
can be iterated reproducibly.
