"""Local browser workbench for PDF-to-model extraction."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlparse
import uuid
from typing import Any

from .schema import DeviceProject
from .service import (
    backend_capabilities,
    digitize_raster_curve,
    extract_pdf_to_session,
    fit_project_for_response,
    generate_model_bundle,
    generate_model_bundle_for_projects,
)


DEFAULT_WEB_OUT = Path("build/webapp")


def serve(host: str = "127.0.0.1", port: int = 8765, out_dir: str | Path = DEFAULT_WEB_OUT) -> ThreadingHTTPServer:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    class Handler(DatasheetWorkbenchHandler):
        workspace = out_path

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"datasheet2spice web app: http://{host}:{server.server_port}")
    server.serve_forever()
    return server


class DatasheetWorkbenchHandler(BaseHTTPRequestHandler):
    workspace = DEFAULT_WEB_OUT

    def do_GET(self) -> None:
        request_path = urlparse(self.path).path
        if request_path in {"/", "/index.html"}:
            self._send_text(INDEX_HTML, "text/html; charset=utf-8")
            return
        if request_path.startswith("/download/"):
            self._send_download(request_path)
            return
        if request_path.startswith("/assets/"):
            self._send_asset(request_path)
            return
        if request_path.startswith("/api/session/"):
            self._send_session_result(request_path)
            return
        if request_path == "/api/capabilities":
            self._send_json(backend_capabilities())
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/api/extract":
            self._handle_extract()
            return
        if self.path == "/api/generate":
            self._handle_generate()
            return
        if self.path == "/api/fit":
            self._handle_fit()
            return
        if self.path == "/api/raster-digitize":
            self._handle_raster_digitize()
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - BaseHTTPRequestHandler API
        print(f"{self.address_string()} - {format % args}")

    def _handle_extract(self) -> None:
        try:
            fields, files = _parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(_content_length(self)))
            if "pdf" not in files:
                self._send_json({"error": "missing PDF file field named 'pdf'"}, HTTPStatus.BAD_REQUEST)
                return
            session = _safe_session(fields.get("session") or str(uuid.uuid4()))
            session_dir = self.workspace / session
            session_dir.mkdir(parents=True, exist_ok=True)
            filename, payload = files["pdf"]
            pdf_path = session_dir / _safe_filename(filename or "upload.pdf")
            pdf_path.write_bytes(payload)
            response = extract_pdf_to_session(
                pdf_path,
                session_dir,
                f"/assets/{session}",
                component_profile=fields.get("component_profile") or "mosfet.power",
            )
            self._send_json(response)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_generate(self) -> None:
        try:
            body = json.loads(self.rfile.read(_content_length(self)).decode("utf-8"))
            session = _safe_session(str(body.get("session") or uuid.uuid4()))
            models = [str(item) for item in body.get("models", ["abm-basic"])]
            dialects = [str(item) for item in body.get("dialects", ["ltspice"])]
            if "projects" in body:
                projects = [DeviceProject(data=item) for item in body["projects"]]
                bundle = generate_model_bundle_for_projects(projects, self.workspace / session / "generated", models, dialects)
            else:
                project = DeviceProject(data=body["project"])
                bundle = generate_model_bundle(project, self.workspace / session / "generated", models, dialects)
            self._send_json(bundle)
        except KeyError as exc:
            self._send_json({"error": f"missing field: {exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_fit(self) -> None:
        try:
            body = json.loads(self.rfile.read(_content_length(self)).decode("utf-8"))
            project = DeviceProject(data=body["project"])
            self._send_json(fit_project_for_response(project))
        except KeyError as exc:
            self._send_json({"error": f"missing field: {exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_raster_digitize(self) -> None:
        try:
            body = json.loads(self.rfile.read(_content_length(self)).decode("utf-8"))
            session = _safe_session(str(body["session"]))
            pdf_path = _session_pdf_path(self.workspace / session, body.get("filename"))
            result = digitize_raster_curve(
                pdf_path,
                int(body["page"]),
                [float(v) for v in body["plot_rect"]],
                curve_name=str(body.get("curve_name") or "curve"),
                x_range=_range_tuple(body.get("x_range"), (0.1, 1000.0)),
                y_range=_range_tuple(body.get("y_range"), (1.0, 100000.0)),
                x_values=[float(v) for v in body["x_values"]] if "x_values" in body else None,
                x_log=bool(body.get("x_log", True)),
                y_log=bool(body.get("y_log", True)),
                threshold=int(body.get("threshold", 110)),
                initial_y_fraction=_optional_float(body.get("initial_y_fraction")),
            )
            self._send_json({"ok": True, "digitization": result})
        except KeyError as exc:
            self._send_json({"error": f"missing field: {exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, text: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_download(self, request_path: str) -> None:
        match = re.fullmatch(r"/download/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)", request_path)
        if not match:
            self._send_json({"error": "invalid download path"}, HTTPStatus.BAD_REQUEST)
            return
        path = self.workspace / match.group(1) / "generated" / match.group(2)
        if not path.exists() or not path.is_file():
            self._send_json({"error": "download not found"}, HTTPStatus.NOT_FOUND)
            return
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_asset(self, request_path: str) -> None:
        match = re.fullmatch(r"/assets/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)", request_path)
        if not match:
            self._send_json({"error": "invalid asset path"}, HTTPStatus.BAD_REQUEST)
            return
        path = self.workspace / match.group(1) / "assets" / match.group(2)
        if not path.exists() or not path.is_file():
            self._send_json({"error": "asset not found"}, HTTPStatus.NOT_FOUND)
            return
        payload = path.read_bytes()
        content_type = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_session_result(self, request_path: str) -> None:
        match = re.fullmatch(r"/api/session/([A-Za-z0-9_-]+)", request_path)
        if not match:
            self._send_json({"error": "invalid session path"}, HTTPStatus.BAD_REQUEST)
            return
        path = self.workspace / match.group(1) / "extract_result.json"
        if not path.exists() or not path.is_file():
            self._send_json({"error": "session result not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_text(path.read_text(encoding="utf-8"), "application/json; charset=utf-8")


def _content_length(handler: BaseHTTPRequestHandler) -> int:
    return int(handler.headers.get("Content-Length", "0"))


def _parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    if "multipart/form-data" not in content_type:
        raise ValueError("expected multipart/form-data")
    raw = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    message = BytesParser(policy=default).parsebytes(raw)
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "form-data" not in disposition:
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = (filename, payload)
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, files


def _safe_session(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)[:80] or str(uuid.uuid4())


def _safe_filename(value: str) -> str:
    name = Path(value).name
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return cleaned if cleaned.lower().endswith(".pdf") else f"{cleaned}.pdf"


def _session_pdf_path(session_dir: Path, filename: Any = None) -> Path:
    if filename:
        candidate = session_dir / _safe_filename(str(filename))
        if candidate.exists() and candidate.is_file():
            return candidate
    pdfs = sorted(session_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError("no uploaded PDF found for this session")
    return pdfs[0]


def _range_tuple(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if value is None:
        return default
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError("axis range must be a two-value array")
    return (float(value[0]), float(value[1]))


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>datasheet2spice Workbench</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #202124;
      --muted: #5f6368;
      --line: #d7dce2;
      --panel: #ffffff;
      --bg: #f6f7f9;
      --accent: #0b6bcb;
      --accent-2: #0f7b5f;
      --warn: #a35f00;
      --bad: #b42318;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body { margin: 0; background: var(--bg); color: var(--ink); }
    header {
      display: flex; justify-content: space-between; gap: 16px; align-items: center;
      padding: 16px 24px; border-bottom: 1px solid var(--line); background: #fff;
    }
    h1 { font-size: 20px; margin: 0; letter-spacing: 0; }
    main {
      display: grid; grid-template-columns: 300px minmax(760px, 1.7fr) minmax(380px, .8fr);
      gap: 16px; padding: 16px; max-width: 1880px; margin: 0 auto;
    }
    section {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
      min-width: 0; overflow: hidden;
    }
    section.review-section { overflow: visible; }
    section h2 {
      margin: 0; padding: 12px 14px; font-size: 15px; border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .body { padding: 14px; }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
    input[type="file"], select, textarea {
      width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 9px;
      background: #fff; color: var(--ink);
    }
    textarea { min-height: 380px; resize: vertical; font-family: Consolas, monospace; font-size: 12px; }
    button {
      border: 1px solid #095fb2; background: var(--accent); color: #fff; border-radius: 6px;
      padding: 9px 12px; cursor: pointer; font-weight: 600;
    }
    button.secondary { background: #fff; color: var(--accent); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .stack { display: grid; gap: 12px; }
    .checks label {
      display: flex; align-items: center; gap: 8px; color: var(--ink); margin: 8px 0;
    }
    .status {
      border-left: 4px solid var(--accent-2); background: #f0fbf7; padding: 10px; border-radius: 4px;
      font-size: 13px; color: #174c3d;
    }
    .status.warn { border-left-color: var(--warn); background: #fff8ec; color: #5d3a00; }
    .status.bad { border-left-color: var(--bad); background: #fff1f0; color: #6b1d16; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; background: #fbfcfd; }
    .findings-table tr.finding-row { cursor: pointer; }
    .findings-table tr.finding-row:hover { background: #f7fbff; }
    .findings-table tr.finding-row.active { background: #edf6ff; box-shadow: inset 3px 0 0 var(--accent); }
    .findings-table .field-col { width: 27%; }
    .findings-table .value-col { width: 18%; }
    .findings-table .confidence-col { width: 72px; }
    .source-cell { position: relative; padding-right: 48px; }
    .snippet-text {
      color: var(--muted); line-height: 1.35; max-height: 4.1em; overflow: hidden;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
    }
    .evidence-float-btn {
      position: absolute; top: 7px; right: 8px; width: 32px; height: 32px;
      display: inline-grid; place-items: center; padding: 0; border-radius: 50%;
      border: 1px solid #9ac7f5; background: #f4f9ff; color: var(--accent);
      font-size: 12px; font-weight: 700;
    }
    .evidence-float-btn:hover,
    .evidence-float-btn:focus { background: #e7f2ff; border-color: var(--accent); outline: 2px solid rgba(20, 112, 204, .16); }
    .mono { font-family: Consolas, monospace; }
    .files a { color: var(--accent); text-decoration: none; }
    .preview { white-space: pre-wrap; font-family: Consolas, monospace; font-size: 12px; max-height: 260px; overflow: auto; }
    h3 { font-size: 13px; margin: 8px 0; }
    .compact { max-height: 240px; overflow: auto; font-size: 12px; }
    .review-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .review-grid input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px; }
    .pill { display: inline-block; padding: 2px 6px; border: 1px solid var(--line); border-radius: 999px; margin: 2px 4px 2px 0; }
    .series-box { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fbfcfd; }
    .review-layout { display: block; }
    .panel-title { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
    .evidence-popover {
      position: fixed; z-index: 800; width: min(640px, calc(100vw - 28px));
      max-height: min(620px, calc(100vh - 28px)); overflow: auto;
      border: 1px solid #b6d6f7; border-radius: 8px; padding: 10px;
      background: #fff; box-shadow: 0 18px 42px rgba(18, 35, 55, .23);
    }
    .evidence-popover img {
      width: 100%; max-height: 430px; object-fit: contain; display: block;
      border: 1px solid var(--line); border-radius: 6px; background: #fff;
      cursor: zoom-in;
    }
    .evidence-meta { display: flex; gap: 6px; flex-wrap: wrap; margin: 7px 0; font-size: 12px; }
    .evidence-card { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
    .curve-compare { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
    .curve-compare table { font-size: 11px; }
    .curve-compare .compact { max-height: 210px; }
    .curve-row { cursor: pointer; }
    .curve-row:hover { background: #f7fbff; }
    .image-modal {
      position: fixed; inset: 0; background: rgba(20, 24, 31, .76); z-index: 999;
      display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 10px; padding: 18px;
    }
    .image-modal-bar {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      color: #fff; font-size: 13px;
    }
    .image-modal button { background: #fff; color: var(--ink); border-color: #fff; }
    .image-modal-stage {
      overflow: auto; display: grid; align-items: start; justify-items: center;
      background: rgba(255, 255, 255, .1); border-radius: 8px; padding: 14px;
    }
    .image-modal img {
      max-width: none; max-height: none; width: auto; height: auto;
      background: #fff; border-radius: 6px;
    }
    .tool-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .tool-grid input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px; }
    .raster-result { max-height: 180px; overflow: auto; font-size: 12px; }
    @media (max-width: 1280px) {
      main { grid-template-columns: 1fr; }
      textarea { min-height: 300px; }
    }
    @media (max-width: 900px) {
      .review-layout { grid-template-columns: 1fr; }
      .evidence-popover { width: calc(100vw - 20px); }
    }
  </style>
</head>
<body>
  <header>
    <h1>datasheet2spice Local Workbench</h1>
    <div class="mono" id="sessionLabel"></div>
  </header>
  <main>
    <section>
      <h2>PDF Upload</h2>
      <div class="body stack">
        <div>
          <label for="componentProfile">Component profile</label>
          <select id="componentProfile">
            <option value="mosfet.power">Power MOSFET / SiC MOSFET</option>
            <option value="diode.power">Power Diode / Schottky / SiC Diode</option>
          </select>
        </div>
        <div>
          <label for="pdf">Component datasheet PDF</label>
          <input id="pdf" type="file" accept="application/pdf,.pdf" />
        </div>
        <button id="extractBtn">Upload and Extract</button>
        <div id="extractStatus" class="status">Waiting for a PDF.</div>
        <div id="seriesBox" class="series-box stack" hidden>
          <div id="seriesStatus" class="status warn"></div>
          <div>
            <label for="seriesPartSelect">Series part</label>
            <select id="seriesPartSelect"></select>
          </div>
          <label class="row"><input id="generateAllSeries" type="checkbox"> Generate all detected series parts</label>
        </div>
        <div id="warnings"></div>
      </div>
    </section>

    <section class="review-section">
      <h2>Extraction Results and Evidence</h2>
      <div class="body">
        <div class="review-layout">
          <div class="stack">
            <table class="findings-table">
              <thead><tr><th class="field-col">Field</th><th class="value-col">Value</th><th class="confidence-col">Confidence</th><th>Source Snippet</th></tr></thead>
              <tbody id="findings"></tbody>
            </table>
            <div>
              <h3>Parameter Review</h3>
              <div id="reviewFields" class="review-grid"></div>
              <button class="secondary" id="applyReviewBtn" disabled>Apply Review Values to JSON</button>
            </div>
            <div>
              <h3>Auto-Digitized Curves</h3>
              <div id="curveBox" class="compact"></div>
            </div>
            <div>
              <h3>Detected Tables</h3>
              <div id="tablesBox" class="compact"></div>
            </div>
            <div class="evidence-card">
              <h3>Raster Plot Digitization</h3>
              <div class="tool-grid">
                <label>Page<input id="rasterPage" value="1" /></label>
                <label>Curve Name<input id="rasterCurveName" value="coss_pf" /></label>
                <label>Plot Box x0,y0,x1,y1<input id="rasterRect" placeholder="Example: 120,180,420,360" /></label>
                <label>Threshold<input id="rasterThreshold" value="110" /></label>
                <label>X Range<input id="rasterXRange" value="0.1,1000" /></label>
                <label>Y Range<input id="rasterYRange" value="1,100000" /></label>
                <label>Initial Y Fraction<input id="rasterInitialY" placeholder="Optional, 0 = top" /></label>
              </div>
              <div class="row" style="margin-top: 8px;">
                <button class="secondary" id="rasterBtn" disabled>Digitize Raster Plot</button>
              </div>
              <div id="rasterStatus" class="status">Available after PDF upload.</div>
              <div id="rasterResult" class="raster-result"></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section>
      <h2>Model Generation</h2>
      <div class="body stack">
        <div>
          <label for="projectJson">Project JSON, editable before generation</label>
          <textarea id="projectJson" spellcheck="false"></textarea>
        </div>
        <div class="checks">
          <label data-model-profile="mosfet.power"><input type="checkbox" name="model" value="abm-basic" checked /> ABM Behavioral Model</label>
          <label data-model-profile="mosfet.power"><input type="checkbox" name="model" value="vdmos-static-fast" checked /> VDMOS Compact Model</label>
          <label data-model-profile="diode.power"><input type="checkbox" name="model" value="diode-basic" /> Diode Compact Model</label>
        </div>
        <div>
          <label for="dialect">SPICE Dialect</label>
          <select id="dialect">
            <option value="ltspice">LTspice</option>
            <option value="ngspice">ngspice</option>
            <option value="common">portable common SPICE</option>
            <option value="pspice">PSpice</option>
            <option value="hspice">HSPICE</option>
            <option value="xyce">Xyce</option>
            <option value="qspice">QSPICE experimental</option>
            <option value="all">All Major Dialects</option>
          </select>
        </div>
        <div class="row">
          <button class="secondary" id="fitBtn" disabled>Refit and Evaluate</button>
          <button id="generateBtn" disabled>Generate Model Files</button>
        </div>
        <div id="generateStatus" class="status">Generation is available after extraction.</div>
        <div id="evaluation" class="compact"></div>
        <div class="files" id="files"></div>
        <div class="preview" id="report"></div>
      </div>
    </section>
  </main>
  <script>
    const requestedSession = new URLSearchParams(location.search).get("session");
    const session = requestedSession || crypto.randomUUID();
    let lastExtractData = null;
    let currentEvidence = [];
    let currentFindings = [];
    let currentCurve = null;
    let currentSeries = null;
    let currentVariantProjects = [];
    let currentSeriesVariants = [];
    let selectedEvidenceIndex = -1;
    document.getElementById("sessionLabel").textContent = session;
    document.getElementById("componentProfile").addEventListener("change", () => updateModelControls(true));
    document.getElementById("seriesPartSelect").addEventListener("change", onSeriesPartChange);
    document.getElementById("generateAllSeries").addEventListener("change", updateSeriesGenerateState);
    updateModelControls(true);
    const setStatus = (id, text, kind = "") => {
      const el = document.getElementById(id);
      el.className = "status" + (kind ? " " + kind : "");
      el.textContent = text;
    };
    document.getElementById("extractBtn").addEventListener("click", async () => {
      const file = document.getElementById("pdf").files[0];
      if (!file) { setStatus("extractStatus", "Please choose a PDF first.", "warn"); return; }
      const form = new FormData();
      form.append("session", session);
      form.append("component_profile", document.getElementById("componentProfile").value || "mosfet.power");
      form.append("pdf", file);
      setStatus("extractStatus", "Uploading and extracting...");
      const res = await fetch("/api/extract", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("extractStatus", data.error || "Extraction failed.", "bad"); return; }
      const series = data.series;
      const needsChoice = series && series.parts?.length > 1 && !series.has_default;
      applyExtractionData(
        data,
        needsChoice
          ? `Detected ${series.parts.length} series parts in ${data.filename}. Choose the target part before generation.`
          : `Extracted ${data.project.device.part_number}. Review the JSON on the right.`,
        needsChoice ? "warn" : ""
      );
    });
    if (requestedSession) {
      loadStoredSession(requestedSession);
    }
    async function loadStoredSession(sessionId) {
      setStatus("extractStatus", "Loading stored extraction results...");
      const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}`);
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("extractStatus", data.error || "Session result not found.", "warn"); return; }
      const series = data.series;
      const needsChoice = series && series.parts?.length > 1 && !series.has_default;
      applyExtractionData(
        data,
        needsChoice
          ? `Loaded a series datasheet with ${series.parts.length} parts. Choose the target part before generation.`
          : `Loaded stored extraction results for ${data.project.device.part_number}.`,
        needsChoice ? "warn" : ""
      );
    }
    function applyExtractionData(data, statusText, statusKind = "") {
      lastExtractData = data;
      currentSeries = data.series || null;
      currentVariantProjects = data.variant_projects || [];
      currentSeriesVariants = data.series_variants || [];
      syncProfileFromProject(data.project);
      document.getElementById("projectJson").value = JSON.stringify(data.project, null, 2);
      document.getElementById("generateBtn").disabled = false;
      document.getElementById("fitBtn").disabled = false;
      document.getElementById("applyReviewBtn").disabled = false;
      document.getElementById("rasterBtn").disabled = false;
      renderSeriesSelector();
      setStatus("extractStatus", statusText, statusKind);
      renderWarnings(data.warnings || []);
      renderFindingsTable(data.findings || []);
      renderReviewFields(data.project);
      renderCurve(data.curve_digitization);
      renderTables(data.tables || []);
      selectedEvidenceIndex = -1;
      renderEvidence(data.evidence || []);
      if (currentFindings.length) selectFinding(currentFindings[0].field, false);
      renderEvaluation(data.evaluation, data.fit || []);
    }
    function renderWarnings(warnings) {
      document.getElementById("warnings").innerHTML = warnings.map(w => `<div class="status warn">${escapeHtml(w)}</div>`).join("");
    }
    function renderFindingsTable(findings) {
      currentFindings = findings || [];
      document.getElementById("findings").innerHTML = currentFindings.map((f, idx) => `
        <tr class="finding-row" data-finding-field="${escapeHtml(f.field)}">
          <td class="mono">${escapeHtml(f.field)}</td>
          <td class="mono">${escapeHtml(JSON.stringify(f.value))} ${escapeHtml(f.unit || "")}</td>
          <td>${Math.round((f.confidence || 0) * 100)}%</td>
          <td class="source-cell">
            <div class="snippet-text">${escapeHtml(f.snippet || "")}</div>
            <button type="button" class="evidence-float-btn" data-evidence-hover="1" data-evidence-field="${escapeHtml(f.field)}" title="Hover to preview evidence; click to zoom">EV</button>
          </td>
        </tr>`).join("");
      document.querySelectorAll("[data-finding-field]").forEach(row => {
        row.addEventListener("click", () => selectFinding(row.dataset.findingField, true));
      });
      wireEvidenceTriggers();
    }
    function syncProfileFromProject(project) {
      const profile = project?.component?.profile;
      const select = document.getElementById("componentProfile");
      if (profile && [...select.options].some(option => option.value === profile)) {
        select.value = profile;
      }
      updateModelControls(true);
    }
    function updateModelControls(resetChecks = false) {
      const profile = document.getElementById("componentProfile").value || "mosfet.power";
      document.querySelectorAll("[data-model-profile]").forEach(label => {
        const input = label.querySelector("input[name=model]");
        const visible = label.dataset.modelProfile === profile;
        label.hidden = !visible;
        if (resetChecks && input) input.checked = visible;
      });
    }
    function renderSeriesSelector() {
      const series = currentSeries;
      const box = document.getElementById("seriesBox");
      const select = document.getElementById("seriesPartSelect");
      const generateAll = document.getElementById("generateAllSeries");
      if (!series || !series.parts || series.parts.length <= 1) {
        box.hidden = true;
        generateAll.checked = false;
        return;
      }
      box.hidden = false;
      const needsChoice = !series.has_default;
      document.getElementById("seriesStatus").textContent = needsChoice
        ? `Series datasheet detected: ${series.parts.join(", ")}. No filename match was found.`
        : `Series datasheet detected: ${series.parts.join(", ")}. Default part: ${series.default_part}.`;
      document.getElementById("seriesStatus").className = "status" + (needsChoice ? " warn" : "");
      select.innerHTML =
        (needsChoice ? '<option value="">Choose a part...</option>' : "") +
        series.parts.map(part => `<option value="${escapeHtml(part)}">${escapeHtml(part)}</option>`).join("");
      select.value = needsChoice ? "" : series.selected_part;
      updateSeriesGenerateState();
    }
    function onSeriesPartChange() {
      const part = document.getElementById("seriesPartSelect").value;
      if (!part) {
        updateSeriesGenerateState();
        return;
      }
      const project = currentVariantProjects.find(item => item.device?.part_number === part);
      if (!project) return;
      if (lastExtractData) lastExtractData.project = project;
      if (currentSeries) currentSeries.selected_part = part;
      const variant = currentSeriesVariants.find(item => item.part_number === part);
      if (variant?.findings) {
        renderFindingsTable(variant.findings);
        if (currentFindings.length) selectFinding(currentFindings[0].field, false);
      }
      if (variant?.warnings) renderWarnings(variant.warnings);
      document.getElementById("projectJson").value = JSON.stringify(project, null, 2);
      renderReviewFields(project);
      document.getElementById("generateBtn").disabled = false;
      setStatus("extractStatus", `Selected ${part}. Review the JSON before generation.`);
    }
    function updateSeriesGenerateState() {
      if (!lastExtractData) {
        document.getElementById("generateBtn").disabled = true;
        return;
      }
      const needsChoice = currentSeries && currentSeries.parts?.length > 1 && !currentSeries.has_default && !document.getElementById("seriesPartSelect").value;
      const generateAll = document.getElementById("generateAllSeries").checked && currentVariantProjects.length > 1;
      document.getElementById("generateBtn").disabled = Boolean(needsChoice && !generateAll);
      if (needsChoice && generateAll) setStatus("extractStatus", "All detected series parts will be generated.");
    }
    document.getElementById("applyReviewBtn").addEventListener("click", () => {
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("extractStatus", "Invalid JSON: " + err.message, "bad"); return; }
      for (const input of document.querySelectorAll("[data-path]")) {
        const raw = input.value.trim();
        if (raw === "") continue;
        setPath(project, input.dataset.path, Number.isFinite(Number(raw)) ? Number(raw) : raw);
      }
      document.getElementById("projectJson").value = JSON.stringify(project, null, 2);
      setStatus("extractStatus", "Review values have been written to JSON.");
    });
    document.getElementById("fitBtn").addEventListener("click", async () => {
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("generateStatus", "Invalid JSON: " + err.message, "bad"); return; }
      setStatus("generateStatus", "Fitting and evaluating...");
      const res = await fetch("/api/fit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session, project })
      });
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("generateStatus", data.error || "Fitting failed.", "bad"); return; }
      document.getElementById("projectJson").value = JSON.stringify(data.project, null, 2);
      renderEvaluation(data.evaluation, data.fit || []);
      setStatus("generateStatus", "Fit and evaluation updated.");
    });
    document.getElementById("rasterBtn").addEventListener("click", async () => {
      if (!lastExtractData) { setStatus("rasterStatus", "Please upload a PDF first.", "warn"); return; }
      const rect = parseNumberList(document.getElementById("rasterRect").value, 4);
      const xRange = parseNumberList(document.getElementById("rasterXRange").value, 2);
      const yRange = parseNumberList(document.getElementById("rasterYRange").value, 2);
      if (!rect || !xRange || !yRange) {
        setStatus("rasterStatus", "Check the plot box and coordinate ranges.", "bad");
        return;
      }
      const initialYRaw = document.getElementById("rasterInitialY").value.trim();
      const body = {
        session,
        filename: lastExtractData.filename,
        page: Number(document.getElementById("rasterPage").value || 1),
        plot_rect: rect,
        curve_name: document.getElementById("rasterCurveName").value.trim() || "curve",
        threshold: Number(document.getElementById("rasterThreshold").value || 110),
        x_range: xRange,
        y_range: yRange,
        initial_y_fraction: initialYRaw === "" ? null : Number(initialYRaw)
      };
      setStatus("rasterStatus", "Digitizing raster plot...");
      const res = await fetch("/api/raster-digitize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("rasterStatus", data.error || "Digitization failed.", "bad"); return; }
      renderRasterResult(data.digitization);
      setStatus("rasterStatus", `Extracted ${data.digitization.metrics.extracted_points}/${data.digitization.metrics.requested_points} points with ${Math.round(data.digitization.confidence * 100)}% confidence.`);
    });
    document.getElementById("generateBtn").addEventListener("click", async () => {
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("generateStatus", "Invalid JSON: " + err.message, "bad"); return; }
      syncProfileFromProject(project);
      const models = [...document.querySelectorAll("input[name=model]:checked")].map(el => el.value);
      const dialect = document.getElementById("dialect").value;
      const dialects = dialect === "all" ? ["common", "ltspice", "ngspice", "pspice", "hspice", "xyce", "qspice"] : [dialect];
      if (!models.length) { setStatus("generateStatus", "Select at least one model family.", "warn"); return; }
      const generateAll = document.getElementById("generateAllSeries").checked && currentVariantProjects.length > 1;
      const body = generateAll ? { session, projects: currentVariantProjects, models, dialects } : { session, project, models, dialects };
      setStatus("generateStatus", "Generating models...");
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok || !data.ok) { setStatus("generateStatus", (data.errors || [data.error]).join("; "), "bad"); return; }
      setStatus("generateStatus", `Generated ${data.files.length} files.`);
      renderEvaluation(data.evaluation, data.fit || []);
      document.getElementById("files").innerHTML = `<a href="${data.download_url}">Download ZIP model bundle</a><br>` +
        data.files.map(f => `<span class="mono">${escapeHtml(f.name)}</span>`).join("<br>");
      document.getElementById("report").textContent = data.report || "";
    });
    function renderReviewFields(project) {
      const isDiode = project?.component?.profile === "diode.power" || project?.component?.family === "diode";
      const fields = isDiode ? [
        ["ratings.vrrm_v", "VRRM (V)"],
        ["ratings.if_av_a", "IF(AV) (A)"],
        ["ratings.ifsm_a", "IFSM (A)"],
        ["static.forward_voltage.vf_v", "VF (V)"],
        ["static.forward_voltage.if_a", "IF test (A)"],
        ["static.leakage.ir_ua", "IR (uA)"],
        ["dynamic.junction_capacitance.cj0_pf", "Cj0 (pF)"],
        ["dynamic.reverse_recovery.trr_ns", "trr (ns)"],
        ["dynamic.reverse_recovery.qrr_nc", "Qrr (nC)"],
        ["thermal.rth_jc_c_per_w", "RthJC (C/W)"]
      ] : [
        ["ratings.vdss_v", "VDSS (V)"],
        ["ratings.id_cont_a", "ID cont (A)"],
        ["ratings.vgs_on_v", "VGS on (V)"],
        ["ratings.vgs_off_v", "VGS off (V)"],
        ["static.vgs_th_v.25", "VGS(th) 25C (V)"],
        ["static.rds_on_mohm.25", "RDS(on) 25C (mOhm)"],
        ["static.gfs_s", "gfs (S)"],
        ["static.rg_int_ohm", "RG int (Ohm)"],
        ["dynamic.gate_charge.qg_nc", "Qg (nC)"],
        ["dynamic.gate_charge.qgs_nc", "Qgs (nC)"],
        ["dynamic.gate_charge.qgd_nc", "Qgd (nC)"],
        ["dynamic.body_diode.qrr_nc", "Qrr (nC)"],
        ["dynamic.body_diode.trr_ns", "trr (ns)"],
        ["dynamic.body_diode.irrm_a", "Irrm (A)"]
      ];
      document.getElementById("reviewFields").innerHTML = fields.map(([path, label]) => `
        <label>${escapeHtml(label)}<input data-path="${escapeHtml(path)}" value="${escapeHtml(getPath(project, path) ?? "")}"></label>
      `).join("");
    }
    function renderCurve(curve) {
      currentCurve = curve;
      if (!curve) { document.getElementById("curveBox").innerHTML = `<div class="status warn">No auto-digitized Ciss/Coss/Crss vector curve was found.</div>`; return; }
      const data = curve.data || {};
      const rows = (data.vds_v || []).map((v, i) => `
        <tr class="curve-row"><td>${v}</td><td>${data.ciss_pf[i]}</td><td>${data.coss_pf[i]}</td><td>${data.crss_pf[i]}</td></tr>
      `).join("");
      document.getElementById("curveBox").innerHTML = `
        <div class="row">
          <span class="pill">page ${curve.page}</span>
          <span class="pill">confidence ${Math.round(curve.confidence * 100)}%</span>
          <button class="secondary" id="curveEvidenceBtn" data-evidence-hover="1" data-evidence-kind="curve">Preview Source Plot</button>
        </div>
        <table><thead><tr><th>VDS</th><th>Ciss</th><th>Coss</th><th>Crss</th></tr></thead><tbody>${rows}</tbody></table>
      `;
      document.querySelectorAll(".curve-row").forEach(row => row.addEventListener("click", event => selectCurveEvidence(event.currentTarget)));
    }
    function renderTables(tables) {
      if (!tables.length) { document.getElementById("tablesBox").textContent = "No table candidates were detected."; return; }
      document.getElementById("tablesBox").innerHTML = tables.slice(0, 4).map(table => `
        <div class="status"><b>page ${table.page}</b> score ${Math.round(table.score * 100)}%</div>
        <table><tbody>${table.rows.slice(0, 6).map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>
      `).join("");
    }
    function selectFinding(field, showPreview = false) {
      if (!field) return;
      document.querySelectorAll("[data-finding-field]").forEach(row => {
        row.classList.toggle("active", row.dataset.findingField === field);
      });
      if (showPreview) {
        const trigger = [...document.querySelectorAll("[data-evidence-field]")].find(btn => btn.dataset.evidenceField === field);
        const item = evidenceForField(field);
        if (trigger && item) showEvidencePopover(trigger, item);
      }
    }
    function evidenceForField(field) {
      const exact = currentEvidence.find(item => item.kind === "field_finding" && item.field === field);
      if (exact) return exact;
      const finding = currentFindings.find(item => item.field === field);
      if (!finding || !finding.page) return null;
      return currentEvidence.find(item => Number(item.page) === Number(finding.page)) || null;
    }
    function curveEvidenceItem() {
      return currentEvidence.find(item => item.kind === "curve_plot") || null;
    }
    function selectCurveEvidence(anchor) {
      const item = curveEvidenceItem();
      if (!item) return;
      document.querySelectorAll("[data-finding-field]").forEach(row => row.classList.remove("active"));
      showEvidencePopover(anchor || document.getElementById("curveEvidenceBtn"), item);
    }
    function renderEvidence(evidence) {
      if (!evidence.length) {
        currentEvidence = [];
        selectedEvidenceIndex = -1;
        wireEvidenceTriggers();
        return;
      }
      currentEvidence = evidence;
      if (selectedEvidenceIndex < 0 || selectedEvidenceIndex >= evidence.length) {
        const preferredIndex = evidence.findIndex(item => item.kind === "curve_plot");
        selectedEvidenceIndex = preferredIndex >= 0 ? preferredIndex : 0;
      }
      wireEvidenceTriggers();
      const curveEvidence = evidence.find(item => item.kind === "curve_plot" && item.bbox);
      if (curveEvidence && !document.getElementById("rasterRect").value.trim()) fillRasterFromEvidence(curveEvidence);
    }
    function evidenceItemForTrigger(trigger) {
      if (trigger.dataset.evidenceKind === "curve") return curveEvidenceItem();
      if (trigger.dataset.evidenceField) return evidenceForField(trigger.dataset.evidenceField);
      return null;
    }
    function wireEvidenceTriggers() {
      document.querySelectorAll("[data-evidence-hover]").forEach(trigger => {
        if (trigger.dataset.evidenceWired) return;
        trigger.dataset.evidenceWired = "1";
        trigger.addEventListener("mouseenter", () => {
          const item = evidenceItemForTrigger(trigger);
          if (item) showEvidencePopover(trigger, item);
        });
        trigger.addEventListener("mouseleave", () => hideEvidencePopover(180));
        trigger.addEventListener("focus", () => {
          const item = evidenceItemForTrigger(trigger);
          if (item) showEvidencePopover(trigger, item);
        });
        trigger.addEventListener("blur", () => hideEvidencePopover(120));
        trigger.addEventListener("click", event => {
          event.stopPropagation();
          const item = evidenceItemForTrigger(trigger);
          if (item) openEvidenceImage(item);
        });
      });
    }
    let evidencePopover = null;
    let evidencePopoverTimer = null;
    function hideEvidencePopover(delay = 0) {
      clearTimeout(evidencePopoverTimer);
      evidencePopoverTimer = setTimeout(() => {
        if (evidencePopover) {
          evidencePopover.remove();
          evidencePopover = null;
        }
      }, delay);
    }
    function showEvidencePopover(anchor, item) {
      if (!anchor || !item || !item.url) return;
      clearTimeout(evidencePopoverTimer);
      if (evidencePopover) evidencePopover.remove();
      const imageUrl = item.detail_url || item.url;
      const bbox = item.detail_bbox || item.bbox || [];
      const popover = document.createElement("div");
      popover.className = "evidence-popover";
      popover.innerHTML = `
        <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(evidenceTitle(item))}" data-popover-zoom="1" />
        <div class="evidence-meta">
          <span class="pill">${escapeHtml(evidenceTitle(item))}</span>
          <span class="pill">page ${escapeHtml(item.page || "")}</span>
          ${item.confidence != null ? `<span class="pill">${Math.round(item.confidence * 100)}%</span>` : ""}
          ${item.score != null ? `<span class="pill">score ${Math.round(item.score * 100)}%</span>` : ""}
        </div>
        <div class="mono">${escapeHtml(bbox.join(", "))}</div>
        <div class="row" style="margin-top: 7px;">
          <button class="secondary" data-popover-open="1">Open Large View</button>
          ${item.bbox ? `<button class="secondary" data-popover-fill="1">Use as Raster Box</button>` : ""}
        </div>
      `;
      popover.addEventListener("mouseenter", () => clearTimeout(evidencePopoverTimer));
      popover.addEventListener("mouseleave", () => hideEvidencePopover(160));
      popover.querySelector("[data-popover-zoom]").addEventListener("click", () => openEvidenceImage(item));
      popover.querySelector("[data-popover-open]").addEventListener("click", () => openEvidenceImage(item));
      const fillButton = popover.querySelector("[data-popover-fill]");
      if (fillButton) fillButton.addEventListener("click", () => fillRasterFromEvidence(item));
      document.body.appendChild(popover);
      evidencePopover = popover;
      positionEvidencePopover(anchor, popover);
      popover.querySelector("img").addEventListener("load", () => positionEvidencePopover(anchor, popover), { once: true });
    }
    function positionEvidencePopover(anchor, popover) {
      const margin = 10;
      const rect = anchor.getBoundingClientRect();
      const popRect = popover.getBoundingClientRect();
      let left = Math.min(window.innerWidth - popRect.width - margin, Math.max(margin, rect.right - popRect.width));
      let top = rect.bottom + 8;
      if (top + popRect.height > window.innerHeight - margin && rect.top - popRect.height - 8 > margin) {
        top = rect.top - popRect.height - 8;
      } else {
        top = Math.min(top, window.innerHeight - popRect.height - margin);
      }
      popover.style.left = `${Math.max(margin, left)}px`;
      popover.style.top = `${Math.max(margin, top)}px`;
    }
    function openEvidenceImage(item) {
      if (!item || !item.url) return;
      hideEvidencePopover(0);
      const existing = document.querySelector(".image-modal");
      if (existing) existing.remove();
      const imageUrl = item.detail_url || item.url;
      const bbox = item.detail_bbox || item.bbox || [];
      const modal = document.createElement("div");
      modal.className = "image-modal";
      modal.innerHTML = `
        <div class="image-modal-bar">
          <div><b>${escapeHtml(evidenceTitle(item))}</b> - page ${escapeHtml(item.page || "")} - ${escapeHtml(bbox.join(", "))}</div>
          <button type="button" data-modal-close="1">Close</button>
        </div>
        <div class="image-modal-stage">
          <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(evidenceTitle(item))}" />
        </div>
      `;
      modal.addEventListener("click", event => {
        if (event.target === modal || event.target.dataset.modalClose) modal.remove();
      });
      document.addEventListener("keydown", function closeOnEscape(event) {
        if (event.key === "Escape") {
          modal.remove();
          document.removeEventListener("keydown", closeOnEscape);
        }
      });
      document.body.appendChild(modal);
    }
    function evidenceTitle(item) {
      if (item.kind === "field_finding") return item.field || "Parameter Evidence";
      const labels = {
        curve_plot: "Curve Plot",
        table_candidate: "Table Evidence",
        page_context: "Page Context"
      };
      return labels[item.kind] || item.label || item.kind || "Screenshot Evidence";
    }
    function fillRasterFromEvidence(item) {
      document.getElementById("rasterPage").value = item.page || 1;
      document.getElementById("rasterRect").value = (item.bbox || []).join(",");
    }
    function renderRasterResult(result) {
      const rows = (result.points || []).map(point => `
        <tr><td>${point.x}</td><td>${point.y}</td><td>${Math.round(point.x_px)}, ${Math.round(point.y_px)}</td></tr>
      `).join("");
      document.getElementById("rasterResult").innerHTML = `
        <div>${(result.notes || []).map(note => `<div class="status warn">${escapeHtml(note)}</div>`).join("")}</div>
        <table><thead><tr><th>X</th><th>${escapeHtml(result.curve_name)}</th><th>Pixel</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }
    function renderEvaluation(evaluation, fits) {
      if (!evaluation) { document.getElementById("evaluation").textContent = ""; return; }
      const fitRows = (fits || []).map(f => `<tr><td>${escapeHtml(f.model)}</td><td class="mono">${escapeHtml(JSON.stringify(f.parameters))}</td></tr>`).join("");
      document.getElementById("evaluation").innerHTML = `
        <div class="status"><b>Quality score ${evaluation.overall_score}/100</b>, grade ${escapeHtml(evaluation.grade)}</div>
        <div>${Object.entries(evaluation.scores || {}).map(([k,v]) => `<span class="pill">${escapeHtml(k)} ${Math.round(v * 100)}%</span>`).join("")}</div>
        <div>${(evaluation.notes || []).map(n => `<div class="status warn">${escapeHtml(n)}</div>`).join("")}</div>
        <table><thead><tr><th>Model</th><th>Fit Parameters</th></tr></thead><tbody>${fitRows}</tbody></table>
      `;
    }
    function getPath(obj, path) {
      return path.split(".").reduce((cur, key) => cur && cur[key] !== undefined ? cur[key] : undefined, obj);
    }
    function setPath(obj, path, value) {
      const parts = path.split(".");
      let cur = obj;
      for (const key of parts.slice(0, -1)) {
        if (!cur[key] || typeof cur[key] !== "object") cur[key] = {};
        cur = cur[key];
      }
      cur[parts[parts.length - 1]] = value;
    }
    function parseNumberList(text, expectedLength) {
      const values = text.split(",").map(v => Number(v.trim())).filter(v => Number.isFinite(v));
      return values.length === expectedLength ? values : null;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
  </script>
</body>
</html>
"""
