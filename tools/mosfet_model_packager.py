#!/usr/bin/env python3
"""Generate first-pass behavioral MOSFET SPICE models from a JSON file.

The generated model is intentionally simple: it is meant as a transparent
starting point for double-pulse transient fitting, not as a foundry-grade
physics model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent


def pair_table(xs: list[float], ys: list[float], suffix: str = "") -> str:
    if len(xs) != len(ys):
        raise ValueError("table x/y lengths do not match")
    chunks: list[str] = []
    for x, y in zip(xs, ys):
        chunks.append(f"{x:g},{y:g}{suffix}")
    return ", ".join(chunks)


def temp_table(values: dict[str, float], suffix: str = "") -> str:
    pairs = sorted((float(k), float(v)) for k, v in values.items())
    return ", ".join(f"{t:g},{v:g}{suffix}" for t, v in pairs)


def wrap_continuation(expr: str, width: int = 92) -> str:
    parts = expr.split(", ")
    lines: list[str] = []
    line = ""
    for part in parts:
        candidate = part if not line else f"{line}, {part}"
        if len(candidate) > width and line:
            lines.append(line + ",")
            line = part
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\n+ ".join(lines)


def clean_spice(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        if line.startswith("+"):
            cleaned.append(line)
        else:
            cleaned.append(line.lstrip())
    return "\n".join(cleaned).rstrip() + "\n"


def render_lib(data: dict, dialect: str = "common") -> str:
    dev = data["device"]
    e = data["electrical_typ"]
    caps = data["capacitance_digitized"]
    paras = data["default_parasitics"]
    rds_table = wrap_continuation(temp_table(e["rds_on_mohm"], "m"))
    vth_table = wrap_continuation(temp_table(e["vgs_th_v"]))
    ciss_table = wrap_continuation(pair_table(caps["vds_v"], caps["ciss_pf"], "p"))
    coss_table = wrap_continuation(pair_table(caps["vds_v"], caps["coss_pf"], "p"))
    crss_table = wrap_continuation(pair_table(caps["vds_v"], caps["crss_pf"], "p"))
    tt_ns = e["body_diode"]["qrr_nc"] / 68.0
    channel = e.get("channel_fit", {})
    ids_ref = float(channel.get("idsat_reference_a", 68.0))
    vgs_ref = float(channel.get("vgs_reference_v", 9.5))
    vth_ref = float(e["vgs_th_v"].get("25", 3.8))
    kid = ids_ref / max((vgs_ref - vth_ref) ** 2, 1e-6)

    if dialect == "common":
        model_scope = "PSpice/SIMetrix-style common ABM transient model."
        clamp_expr = "min(max(abs(v),0.1),1000)"
        ch = "Gch d_int s_int VALUE = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Ggs g_int s_int VALUE = {CGS_F(V(d_int,s_int))*DDT(V(g_int,s_int))}"
        gd = "Ggd g_int d_int VALUE = {CGD_F(V(d_int,s_int))*DDT(V(g_int,d_int))}"
        ds = "Gds d_int s_int VALUE = {CDS_F(V(d_int,s_int))*DDT(V(d_int,s_int))}"
    elif dialect == "ltspice":
        model_scope = "LTspice 26 behavioral-source transient model."
        clamp_expr = "limit(abs(v),0.1,1000)"
        ch = "Bch d_int s_int I = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Bgs g_int s_int I = {CGS_F(V(d_int,s_int))*ddt(V(g_int,s_int))}"
        gd = "Bgd g_int d_int I = {CGD_F(V(d_int,s_int))*ddt(V(g_int,d_int))}"
        ds = "Bds d_int s_int I = {CDS_F(V(d_int,s_int))*ddt(V(d_int,s_int))}"
    elif dialect == "ngspice":
        model_scope = "ngspice/SPICE3 ABM transient model."
        clamp_expr = "min(max(abs(v),0.1),1000)"
        ch = "Bch d_int s_int I = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Bgs g_int s_int I = {CGS_F(V(d_int,s_int))*DDT(V(g_int,s_int))}"
        gd = "Bgd g_int d_int I = {CGD_F(V(d_int,s_int))*DDT(V(g_int,d_int))}"
        ds = "Bds d_int s_int I = {CDS_F(V(d_int,s_int))*DDT(V(d_int,s_int))}"
    else:
        raise ValueError(f"unknown dialect: {dialect}")

    return clean_spice(dedent(
        f"""\
        * {dev} first-pass behavioral MOSFET model
        * Source datasheet: {data["datasheet"]}, {data["datasheet_rev"]}
        * Scope: {model_scope}
        * Caveat: capacitance curves are datasheet vector extractions and still
        *         should be fitted against measured double-pulse waveforms.
        *
        * Pins: D G S
        * Parameters:
        *   TJ         Junction temperature used for Vth/Rds interpolation [degC]
        *   LD, LS, LG External drain/source/gate stray inductance
        *   RGEXT      External series gate resistance, added to datasheet RG
        *   *_SCALE    Fitting multipliers for measured waveform calibration

        .subckt {dev} D G S PARAMS: TJ=25 LD={paras["ld_nh"]}n LS={paras["ls_nh"]}n LG={paras["lg_nh"]}n RGEXT={paras["rg_ext_ohm"]} RON_SCALE=1 CGS_SCALE=1 CGD_SCALE=1 CDS_SCALE=1 DIODE_SCALE=1 VSMOOTH=0.35

        .param RGINT={e["rg_int_ohm"]}
        .param ROFF=1e9
        .param KID={kid:.6g}
        .param RON={{RON_SCALE*table(TJ, {rds_table})}}
        .param VTH={{table(TJ, {vth_table})}}

        .func VDSX(v) {{{clamp_expr}}}
        .func VOV_F(vgs) {{0.5*((vgs-VTH)+sqrt((vgs-VTH)*(vgs-VTH)+VSMOOTH*VSMOOTH))}}
        .func IDSAT_F(vgs) {{max(KID*VOV_F(vgs)*VOV_F(vgs),1u)}}
        .func CISS_F(v) {{table(VDSX(v), {ciss_table})}}
        .func COSS_F(v) {{table(VDSX(v), {coss_table})}}
        .func CRSS_F(v) {{table(VDSX(v), {crss_table})}}
        .func CGS_F(v) {{CGS_SCALE*max(CISS_F(v)-CRSS_F(v),1p)}}
        .func CGD_F(v) {{CGD_SCALE*max(CRSS_F(v),1p)}}
        .func CDS_F(v) {{CDS_SCALE*max(COSS_F(v)-CRSS_F(v),1p)}}
        .func GATEON(vgs) {{0.5*(1+tanh((vgs-VTH)/VSMOOTH))}}

        Ld D d_int {{LD}}
        Lg G g_pad {{LG}}
        Ls S s_int {{LS}}
        Rg g_pad g_int {{RGINT+RGEXT}}

        * Bidirectional smooth channel: low VDS slope follows Rds(on), high VDS is limited by Idsat(Vgs).
        {ch}

        * Nonlinear capacitances. Coss is split into Cgd=Crss and Cds=Coss-Crss.
        {gs}
        {gd}
        {ds}

        * Source-to-drain body diode. Rs/TT are fit starters from VSD and Qrr/trr.
        Dbody s_int d_int DBODY
        .model DBODY D(Is=1e-12 N=2 Rs=31m Cjo=209p M=0.45 Vj=1.0 Tt={tt_ns:.3g}n BV=1200 Ibv=30m)

        * Very small gate leakage path for numerical conditioning.
        Rgate_leak g_int s_int 1e12

        * DIODE_SCALE is reserved for simulators whose diode-area expression syntax is known.
        .ends {dev}
        """
    ))


def render_double_pulse(data: dict, model_file: str = "S4661_behavioral.lib") -> str:
    dev = data["device"]
    paras = data["default_parasitics"]
    v_on = data["ratings"]["vgs_on_v"]
    v_off = data["ratings"]["vgs_off_v"]
    return clean_spice(dedent(
        f"""\
        * {dev} low-side inductive double-pulse starter deck
        * Run in a SPICE simulator with behavioral-source/ABM support.
        * This is a topology/syntax starter, not a validated lab fixture.

        .include {model_file}

        Vbus bus 0 800
        Rload bus nload 20m
        Lload nload drain 250u
        Dfw drain bus DFAST
        .model DFAST D(Is=1e-15 N=1.5 Rs=20m Cjo=80p Tt=20n BV=1200 Ibv=1m)

        * First pulse is about 21 us so 800 V / 250 uH reaches roughly 68 A.
        Vdrv gate_drv 0 PULSE({v_off} {v_on} 100n 5n 5n 21u 25u 2)
        Rdrv gate_drv gate {paras["rg_ext_ohm"]}
        XQ drain gate 0 {dev} PARAMS: TJ=25 LD={paras["ld_nh"]}n LS={paras["ls_nh"]}n LG=0.2n RGEXT=0

        .tran 0 26.5u 0 1n
        .save V(drain) V(gate) V(gate_drv) I(Lload) I(Vbus)
        .options plotwinsize=0 reltol=0.003 abstol=1n vntol=1u
        .end
        """
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("params", type=Path, help="MOSFET parameter JSON")
    parser.add_argument("--out", type=Path, default=Path("."), help="output directory")
    parser.add_argument(
        "--dialect",
        choices=["common", "ltspice", "ngspice", "all"],
        default="all",
        help="model dialect to generate; default writes common, LTspice, and ngspice variants",
    )
    args = parser.parse_args()

    data = json.loads(args.params.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    dev = data["device"]
    dialects = ["common", "ltspice", "ngspice"] if args.dialect == "all" else [args.dialect]
    for dialect in dialects:
        suffix = "" if dialect == "common" else f"_{dialect}"
        lib = args.out / f"{dev}_behavioral{suffix}.lib"
        cir = args.out / f"{dev}_double_pulse_example{suffix}.cir"
        lib.write_text(render_lib(data, dialect=dialect), encoding="utf-8", newline="\n")
        cir.write_text(render_double_pulse(data, model_file=lib.name), encoding="utf-8", newline="\n")
        print(lib)
        print(cir)


if __name__ == "__main__":
    main()
