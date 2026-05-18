"""Markdown reporting."""

from __future__ import annotations

from .schema import DeviceProject


def render_report(project: DeviceProject) -> str:
    data = project.data
    device = data.get("device", {})
    ratings = data.get("ratings", {})
    static = data.get("static", {})
    dynamic = data.get("dynamic", {})
    lines = [
        f"# {project.part_number} datasheet2spice report",
        "",
        f"- Vendor: {device.get('vendor', '')}",
        f"- Type: {device.get('type', '')}",
        f"- Datasheet: {device.get('datasheet', '')}",
        "",
        "## Ratings",
        "",
    ]
    for key, value in ratings.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Static Parameters", ""]
    for key, value in static.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Dynamic Parameters", ""]
    for key, value in dynamic.items():
        if key != "capacitance":
            lines.append(f"- `{key}`: {value}")
    cap = dynamic.get("capacitance", {})
    if cap:
        n = len(cap.get("vds_v", []))
        lines += ["", "## Curves", "", f"- capacitance points: {n}", f"- source: {cap.get('source', '')}"]
    lines += [
        "",
        "## Model Caveat",
        "",
        "Generated models are starting points. Validate against datasheet test conditions and lab waveforms before design use.",
        "",
    ]
    return "\n".join(lines)
