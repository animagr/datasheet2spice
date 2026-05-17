"""ABM behavioral model emitter."""

from __future__ import annotations

from textwrap import dedent

from ..curves import table_pairs
from ..dialects import SUPPORTED_DIALECTS, dialect_suffix
from ..plugins import emitter
from ..schema import DeviceProject


def _clean(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lines.append(line if line.startswith("+") else line.lstrip())
    return "\n".join(lines).rstrip() + "\n"


def _wrap_table(expr: str, width: int = 92) -> str:
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


def _temp_table(values: dict[str, float], suffix: str = "") -> str:
    pairs = sorted((float(k), float(v)) for k, v in values.items())
    return ", ".join(f"{t:g},{v:g}{suffix}" for t, v in pairs)


@emitter("abm-basic")
class AbmBasicEmitter:
    name = "abm-basic"

    def emit(self, project: DeviceProject, dialect: str = "common") -> dict[str, str]:
        if dialect not in SUPPORTED_DIALECTS:
            raise ValueError(f"unsupported ABM dialect: {dialect}")
        model = _render_lib(project, dialect)
        deck = _render_double_pulse(project, _lib_name(project, dialect))
        suffix = dialect_suffix(dialect)
        return {
            _lib_name(project, dialect): model,
            f"{project.model_name}_double_pulse_abm{suffix}.cir": deck,
        }


def _lib_name(project: DeviceProject, dialect: str) -> str:
    suffix = dialect_suffix(dialect)
    return f"{project.model_name}_abm{suffix}.lib"


def _render_lib(project: DeviceProject, dialect: str) -> str:
    name = project.model_name
    static = project.get_path("static", default={})
    dyn = project.get_path("dynamic", default={})
    caps = project.require_path("dynamic", "capacitance")
    paras = project.get_path("parasitics", default={})
    body = dyn.get("body_diode", {})
    channel = dyn.get("channel_fit", {})

    rds_table = _wrap_table(_temp_table(static.get("rds_on_mohm", {"25": 10}), "m"))
    vth_table = _wrap_table(_temp_table(static.get("vgs_th_v", {"25": 4.0})))
    vds = [float(x) for x in caps["vds_v"]]
    ciss = [float(x) for x in caps["ciss_pf"]]
    coss = [float(x) for x in caps["coss_pf"]]
    crss = [float(x) for x in caps["crss_pf"]]
    ciss_table = _wrap_table(table_pairs(vds, ciss, "p"))
    coss_table = _wrap_table(table_pairs(vds, coss, "p"))
    crss_table = _wrap_table(table_pairs(vds, crss, "p"))

    ids_ref = float(channel.get("idsat_reference_a", 50.0))
    vgs_ref = float(channel.get("vgs_reference_v", 10.0))
    vth_ref = float(static.get("vgs_th_v", {}).get("25", 4.0))
    kid = ids_ref / max((vgs_ref - vth_ref) ** 2, 1e-6)
    qrr_nc = float(body.get("qrr_nc", 0.0) or 0.0)
    tt_ns = qrr_nc / ids_ref if qrr_nc > 0 and ids_ref > 0 else float(body.get("trr_ns", 20.0) or 20.0)

    if dialect in {"common", "pspice"}:
        model_scope = "PSpice/SIMetrix-style common ABM transient model."
        clamp_expr = "min(max(abs(v),0.1),1000)"
        ch = "Gch d_int s_int VALUE = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Ggs g_int s_int VALUE = {CGS_F(V(d_int,s_int))*DDT(V(g_int,s_int))}"
        gd = "Ggd g_int d_int VALUE = {CGD_F(V(d_int,s_int))*DDT(V(g_int,d_int))}"
        ds = "Gds d_int s_int VALUE = {CDS_F(V(d_int,s_int))*DDT(V(d_int,s_int))}"
        if dialect == "pspice":
            model_scope = "PSpice ABM transient model using VALUE-controlled sources."
    elif dialect in {"ltspice", "qspice"}:
        model_scope = "LTspice behavioral-source transient model."
        clamp_expr = "limit(abs(v),0.1,1000)"
        ch = "Bch d_int s_int I = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Bgs g_int s_int I = {CGS_F(V(d_int,s_int))*ddt(V(g_int,s_int))}"
        gd = "Bgd g_int d_int I = {CGD_F(V(d_int,s_int))*ddt(V(g_int,d_int))}"
        ds = "Bds d_int s_int I = {CDS_F(V(d_int,s_int))*ddt(V(d_int,s_int))}"
        if dialect == "qspice":
            model_scope = "QSPICE experimental LTspice-like behavioral-source transient model."
    elif dialect == "hspice":
        model_scope = "HSPICE ABM starter using current-controlled expression sources."
        clamp_expr = "min(max(abs(v),0.1),1000)"
        ch = "Gch d_int s_int CUR='IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))'"
        gs = "Ggs g_int s_int CUR='CGS_F(V(d_int,s_int))*DDT(V(g_int,s_int))'"
        gd = "Ggd g_int d_int CUR='CGD_F(V(d_int,s_int))*DDT(V(g_int,d_int))'"
        ds = "Gds d_int s_int CUR='CDS_F(V(d_int,s_int))*DDT(V(d_int,s_int))'"
    else:
        model_scope = "ngspice/SPICE3 ABM transient model."
        clamp_expr = "min(max(abs(v),0.1),1000)"
        ch = "Bch d_int s_int I = {IDSAT_F(V(g_int,s_int))*tanh(V(d_int,s_int)/(RON*IDSAT_F(V(g_int,s_int))+1m))}"
        gs = "Bgs g_int s_int I = {CGS_F(V(d_int,s_int))*DDT(V(g_int,s_int))}"
        gd = "Bgd g_int d_int I = {CGD_F(V(d_int,s_int))*DDT(V(g_int,d_int))}"
        ds = "Bds d_int s_int I = {CDS_F(V(d_int,s_int))*DDT(V(d_int,s_int))}"
        if dialect == "xyce":
            model_scope = "Xyce/SPICE3 behavioral-source transient model."

    return _clean(dedent(
        f"""\
        * {name} ABM dynamic-basic model generated by datasheet2spice
        * Scope: {model_scope}
        * Pins: D G S
        .subckt {name} D G S PARAMS: TJ=25 LD={float(paras.get("ld_nh", 2.0))}n LS={float(paras.get("ls_nh", 1.0))}n LG={float(paras.get("lg_nh", 0.2))}n RGEXT={float(paras.get("rg_ext_ohm", 4.7))} RON_SCALE=1 CGS_SCALE=1 CGD_SCALE=1 CDS_SCALE=1 VSMOOTH=0.35

        .param RGINT={float(static.get("rg_int_ohm", 0.0) or 0.0):g}
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

        Ld D d_int {{LD}}
        Lg G g_pad {{LG}}
        Ls S s_int {{LS}}
        Rg g_pad g_int {{RGINT+RGEXT}}
        {ch}
        {gs}
        {gd}
        {ds}
        Dbody s_int d_int DBODY
        .model DBODY D(Is=1e-12 N=2 Rs=31m Cjo={max(coss[-1] - crss[-1], 1):g}p M=0.45 Vj=1.0 Tt={tt_ns:.3g}n BV={float(project.get_path("ratings", "vdss_v", default=1200)):g} Ibv=30m)
        Rgate_leak g_int s_int 1e12
        .ends {name}
        """
    ))


def _render_double_pulse(project: DeviceProject, model_file: str) -> str:
    name = project.model_name
    ratings = project.get_path("ratings", default={})
    paras = project.get_path("parasitics", default={})
    vbus = min(float(ratings.get("vdss_v", 1200)) * 2 / 3, 800.0)
    v_on = float(ratings.get("vgs_on_v", 18.0))
    v_off = float(ratings.get("vgs_off_v", -2.0))
    rg = float(paras.get("rg_ext_ohm", 4.7))
    return _clean(dedent(
        f"""\
        * {name} ABM low-side inductive double-pulse starter deck
        .include {model_file}
        Vbus bus 0 {vbus:g}
        Rload bus nload 20m
        Lload nload drain 250u
        Dfw drain bus DFAST
        .model DFAST D(Is=1e-15 N=1.5 Rs=20m Cjo=80p Tt=20n BV={float(ratings.get("vdss_v", 1200)):g} Ibv=1m)
        Vdrv gate_drv 0 PULSE({v_off:g} {v_on:g} 100n 5n 5n 21u 25u 2)
        Rdrv gate_drv gate {rg:g}
        XQ drain gate 0 {name} PARAMS: TJ=25 LG=0.2n RGEXT=0
        .tran 0 26.5u 0 1n
        .save V(drain) V(gate) V(gate_drv) I(Lload) I(Vbus)
        .options plotwinsize=0 reltol=0.003 abstol=1n vntol=1u
        .end
        """
    ))
