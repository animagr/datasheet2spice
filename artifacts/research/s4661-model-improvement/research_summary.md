# S4661 behavioral model improvement research summary

Date: 2026-05-17

## Question

How should a MOSFET behavioral model be built from datasheet data when the target is both good transient accuracy and fast SPICE convergence?

## Sources Checked

- ROHM, New SPICE Models with Improved Simulation Speed for Power Semiconductors: https://fscdn.rohm.com/en/products/databook/white_paper/discrete/sic/mosfet/new_spice_model_for_faster_simulation_of_power_semiconductors_wp-e.pdf
- ROHM, How to Use LTspice Models: Tips for Improving Convergence: https://fscdn.rohm.com/en/products/databook/applinote/common/how_to_use_ltspice_models_tips_for_improving_convergence_an-e.pdf
- ROHM Design Models: https://www.rohm.com/support/design-model
- Nexperia AN90034 Precision Electrothermal models in SPICE and VHDL-AMS for Power MOSFETs: https://assets.nexperia.com/documents/application-note/AN90034.pdf
- Infineon AN 2014-02 Simulation models for Infineon Power MOSFET: https://community.infineon.com/gfawx74859/attachments/gfawx74859/mosfetsisic/6120/1/Infineon-ApplicationNote_PowerMOSFET_SimulationModels-AN-v01_00-EN.pdf
- ORNL, Datasheet driven silicon carbide power MOSFET model: https://www.ornl.gov/publication/datasheet-driven-silicon-carbide-power-mosfet-model
- Nelson et al., Computational Efficiency Analysis of SiC MOSFET Models in SPICE: Dynamic Behavior, DOI 10.1109/OJPEL.2021.3056075: https://doaj.org/article/0bdd76da4bdb4d0fbb338998f7086ab5

## Findings

- Vendor practice separates model intent. ROHM L1 is oriented toward higher static-characteristic precision, while L3 is specialized for dynamic characteristics with better convergence and speed.
- Nonlinear capacitance voltage dependence is essential for switching time and gate charge. The S4661 model should keep Fig.19 data, but a smoothed analytic fit will likely converge better than raw lookup tables.
- Channel current should not be represented as a pure on/off resistor when switching waveforms matter. A continuous Idsat(Vgs) limiter improves the transition from off-state, Miller plateau behavior, and LTspice convergence.
- Parasitic inductance and Kelvin/common-source effects are part of the model/test fixture, not optional decorations. The eventual fitting loop must use real driver, probe, PCB, and load parasitics.
- For LTspice convergence, ROHM recommends smaller maximum timestep, Alternate solver, careful tolerance settings, sloped supplies, and avoiding ideal passive resonances.

## Implemented in this workspace

- `tools/mosfet_model_packager.py` now generates common ABM, LTspice, and ngspice variants.
- The channel model changed from a smooth Rds(on)-only gate switch to a continuous `Idsat(Vgs)` plus `RDS(on)` model.
- `s4661_params.json` now records the channel-fit seed: 68 A at an approximate 9.5 V Miller plateau from Fig.21.
- LTspice run of `S4661_double_pulse_example_ltspice.cir` completed with LTspice 26.0.1. After the channel-model change, the log no longer shows repeated tolerance-relaxation warnings and produced about 26751 transient points.

## Remaining Work

- Digitize Fig.11/Fig.12 transfer curves and fit `Idsat(Vgs,T)` instead of using the Fig.21 Miller-plateau seed.
- Digitize output curves and third-quadrant curves if short-circuit, linear-region, or reverse-conduction accuracy matters.
- Replace capacitance lookup tables with smooth analytic capacitance or charge expressions to reduce discontinuities at table knots.
- Add a realistic gate-driver/clamp model and measured PCB parasitics before judging gate-voltage overshoot.
