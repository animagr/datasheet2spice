"""Local browser workbench for PDF-to-model extraction."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import uuid
import zipfile
from typing import Any

from .evaluation import evaluate_project_model
from .extractors.pdf_mosfet import extract_mosfet_project_from_pdf
from .fitting import fit_project_parameters
from .plugins import load_plugins, registry
from .report import render_report
from .schema import DeviceProject
from .validate import validate_project


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
        if self.path in {"/", "/index.html"}:
            self._send_text(INDEX_HTML, "text/html; charset=utf-8")
            return
        if self.path.startswith("/download/"):
            self._send_download(self.path)
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
            result = extract_mosfet_project_from_pdf(pdf_path)
            project: DeviceProject = result["project"]
            project_path = session_dir / f"{project.model_name}.device.json"
            project.save(project_path)
            self._send_json(
                {
                    "session": session,
                    "filename": pdf_path.name,
                    "project": project.data,
                    "project_path": str(project_path),
                    "findings": result["findings"],
                    "warnings": result["warnings"],
                    "tables": result.get("tables", []),
                    "curve_digitization": result.get("curve_digitization"),
                    "fit": fit_project_parameters(project)["fits"],
                    "evaluation": evaluate_project_model(project),
                }
            )
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_generate(self) -> None:
        try:
            body = json.loads(self.rfile.read(_content_length(self)).decode("utf-8"))
            session = _safe_session(str(body.get("session") or uuid.uuid4()))
            project = DeviceProject(data=body["project"])
            models = [str(item) for item in body.get("models", ["abm-basic"])]
            dialects = [str(item) for item in body.get("dialects", ["ltspice"])]
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
            fit = fit_project_parameters(project)
            self._send_json({"ok": True, "project": fit["project"], "fit": fit["fits"], "evaluation": evaluate_project_model(project)})
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


def generate_model_bundle(project: DeviceProject, out_dir: str | Path, models: list[str], dialects: list[str]) -> dict[str, Any]:
    load_plugins()
    errors = validate_project(project)
    if any(model in {"vdmos-static-fast", "abm-basic"} for model in models) and errors:
        return {"ok": False, "errors": errors, "files": []}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []
    for model in models:
        if model not in registry.emitters:
            return {"ok": False, "errors": [f"unknown emitter: {model}"], "files": []}
        for dialect in dialects:
            emitted = registry.emitters[model].emit(project, dialect=dialect)
            for name, content in emitted.items():
                path = out / name
                path.write_text(content, encoding="utf-8", newline="\n")
                files.append({"name": name, "path": str(path), "content": content})
    report = render_report(project)
    report_path = out / "report.md"
    report_path.write_text(report + "\n", encoding="utf-8")
    files.append({"name": "report.md", "path": str(report_path), "content": report})
    fit = fit_project_parameters(project)
    evaluation = evaluate_project_model(project)
    analysis_path = out / "fit_evaluation.json"
    analysis_path.write_text(json.dumps({"fit": fit["fits"], "evaluation": evaluation}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files.append({"name": "fit_evaluation.json", "path": str(analysis_path), "content": analysis_path.read_text(encoding="utf-8")})

    zip_path = out / f"{project.model_name}_models.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            zf.write(item["path"], arcname=item["name"])
    files.append({"name": zip_path.name, "path": str(zip_path), "content": ""})
    session = out.parent.name
    return {
        "ok": True,
        "errors": [],
        "files": files,
        "download_url": f"/download/{session}/{zip_path.name}",
        "report": report,
        "fit": fit["fits"],
        "evaluation": evaluation,
    }


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


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
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
    body { margin: 0; background: var(--bg); color: var(--ink); }
    header {
      display: flex; justify-content: space-between; gap: 16px; align-items: center;
      padding: 16px 24px; border-bottom: 1px solid var(--line); background: #fff;
    }
    h1 { font-size: 20px; margin: 0; letter-spacing: 0; }
    main {
      display: grid; grid-template-columns: 340px minmax(360px, 1fr) 420px;
      gap: 16px; padding: 16px; max-width: 1500px; margin: 0 auto;
    }
    section {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
      min-width: 0; overflow: hidden;
    }
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
    .mono { font-family: Consolas, monospace; }
    .files a { color: var(--accent); text-decoration: none; }
    .preview { white-space: pre-wrap; font-family: Consolas, monospace; font-size: 12px; max-height: 260px; overflow: auto; }
    h3 { font-size: 13px; margin: 8px 0; }
    .compact { max-height: 240px; overflow: auto; font-size: 12px; }
    .review-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .review-grid input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px; }
    .pill { display: inline-block; padding: 2px 6px; border: 1px solid var(--line); border-radius: 999px; margin: 2px 4px 2px 0; }
    @media (max-width: 1180px) { main { grid-template-columns: 1fr; } textarea { min-height: 300px; } }
  </style>
</head>
<body>
  <header>
    <h1>datasheet2spice 本地工作台</h1>
    <div class="mono" id="sessionLabel"></div>
  </header>
  <main>
    <section>
      <h2>PDF 上传</h2>
      <div class="body stack">
        <div>
          <label for="pdf">MOSFET datasheet PDF</label>
          <input id="pdf" type="file" accept="application/pdf,.pdf" />
        </div>
        <button id="extractBtn">上传并自动提取</button>
        <div id="extractStatus" class="status">等待选择 PDF。</div>
        <div id="warnings"></div>
      </div>
    </section>

    <section>
      <h2>提取结果</h2>
      <div class="body stack">
        <table>
          <thead><tr><th>字段</th><th>值</th><th>置信度</th><th>来源片段</th></tr></thead>
          <tbody id="findings"></tbody>
        </table>
        <div>
          <h3>参数校对</h3>
          <div id="reviewFields" class="review-grid"></div>
          <button class="secondary" id="applyReviewBtn" disabled>应用校对值到 JSON</button>
        </div>
        <div>
          <h3>自动数字化曲线</h3>
          <div id="curveBox" class="compact"></div>
        </div>
        <div>
          <h3>识别到的表格</h3>
          <div id="tablesBox" class="compact"></div>
        </div>
      </div>
    </section>

    <section>
      <h2>模型生成</h2>
      <div class="body stack">
        <div>
          <label for="projectJson">项目 JSON，可先人工修正再生成</label>
          <textarea id="projectJson" spellcheck="false"></textarea>
        </div>
        <div class="checks">
          <label><input type="checkbox" name="model" value="abm-basic" checked /> ABM 行为模型</label>
          <label><input type="checkbox" name="model" value="vdmos-static-fast" checked /> VDMOS 紧凑模型</label>
        </div>
        <div>
          <label for="dialect">SPICE 方言</label>
          <select id="dialect">
            <option value="ltspice">LTspice</option>
            <option value="ngspice">ngspice</option>
            <option value="common">common ABM</option>
            <option value="all">全部</option>
          </select>
        </div>
        <div class="row">
          <button class="secondary" id="fitBtn" disabled>重新拟合并评估</button>
          <button id="generateBtn" disabled>生成模型文件</button>
        </div>
        <div id="generateStatus" class="status">提取成功后可生成。</div>
        <div id="evaluation" class="compact"></div>
        <div class="files" id="files"></div>
        <div class="preview" id="report"></div>
      </div>
    </section>
  </main>
  <script>
    const session = crypto.randomUUID();
    document.getElementById("sessionLabel").textContent = session;
    const setStatus = (id, text, kind = "") => {
      const el = document.getElementById(id);
      el.className = "status" + (kind ? " " + kind : "");
      el.textContent = text;
    };
    document.getElementById("extractBtn").addEventListener("click", async () => {
      const file = document.getElementById("pdf").files[0];
      if (!file) { setStatus("extractStatus", "请先选择 PDF。", "warn"); return; }
      const form = new FormData();
      form.append("session", session);
      form.append("pdf", file);
      setStatus("extractStatus", "正在上传和提取...");
      const res = await fetch("/api/extract", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("extractStatus", data.error || "提取失败", "bad"); return; }
      document.getElementById("projectJson").value = JSON.stringify(data.project, null, 2);
      document.getElementById("generateBtn").disabled = false;
      document.getElementById("fitBtn").disabled = false;
      document.getElementById("applyReviewBtn").disabled = false;
      setStatus("extractStatus", `已提取 ${data.project.device.part_number}，请检查右侧 JSON。`);
      document.getElementById("warnings").innerHTML = (data.warnings || []).map(w => `<div class="status warn">${escapeHtml(w)}</div>`).join("");
      document.getElementById("findings").innerHTML = (data.findings || []).map(f => `
        <tr>
          <td class="mono">${escapeHtml(f.field)}</td>
          <td class="mono">${escapeHtml(JSON.stringify(f.value))} ${escapeHtml(f.unit || "")}</td>
          <td>${Math.round((f.confidence || 0) * 100)}%</td>
          <td>${escapeHtml(f.snippet || "")}</td>
        </tr>`).join("");
      renderReviewFields(data.project);
      renderCurve(data.curve_digitization);
      renderTables(data.tables || []);
      renderEvaluation(data.evaluation, data.fit || []);
    });
    document.getElementById("applyReviewBtn").addEventListener("click", () => {
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("extractStatus", "JSON 格式错误：" + err.message, "bad"); return; }
      for (const input of document.querySelectorAll("[data-path]")) {
        const raw = input.value.trim();
        if (raw === "") continue;
        setPath(project, input.dataset.path, Number.isFinite(Number(raw)) ? Number(raw) : raw);
      }
      document.getElementById("projectJson").value = JSON.stringify(project, null, 2);
      setStatus("extractStatus", "校对值已写入 JSON。");
    });
    document.getElementById("fitBtn").addEventListener("click", async () => {
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("generateStatus", "JSON 格式错误：" + err.message, "bad"); return; }
      setStatus("generateStatus", "正在拟合并评估...");
      const res = await fetch("/api/fit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session, project })
      });
      const data = await res.json();
      if (!res.ok || data.error) { setStatus("generateStatus", data.error || "拟合失败", "bad"); return; }
      document.getElementById("projectJson").value = JSON.stringify(data.project, null, 2);
      renderEvaluation(data.evaluation, data.fit || []);
      setStatus("generateStatus", "拟合和评估已更新。");
    });
    document.getElementById("generateBtn").addEventListener("click", async () => {
      const models = [...document.querySelectorAll("input[name=model]:checked")].map(el => el.value);
      const dialect = document.getElementById("dialect").value;
      const dialects = dialect === "all" ? ["common", "ltspice", "ngspice"] : [dialect];
      if (!models.length) { setStatus("generateStatus", "至少选择一种模型。", "warn"); return; }
      let project;
      try { project = JSON.parse(document.getElementById("projectJson").value); }
      catch (err) { setStatus("generateStatus", "JSON 格式错误：" + err.message, "bad"); return; }
      setStatus("generateStatus", "正在生成模型...");
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session, project, models, dialects })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) { setStatus("generateStatus", (data.errors || [data.error]).join("; "), "bad"); return; }
      setStatus("generateStatus", `已生成 ${data.files.length} 个文件。`);
      renderEvaluation(data.evaluation, data.fit || []);
      document.getElementById("files").innerHTML = `<a href="${data.download_url}">下载 ZIP 模型包</a><br>` +
        data.files.map(f => `<span class="mono">${escapeHtml(f.name)}</span>`).join("<br>");
      document.getElementById("report").textContent = data.report || "";
    });
    function renderReviewFields(project) {
      const fields = [
        ["ratings.vdss_v", "VDSS (V)"],
        ["ratings.id_cont_a", "ID cont (A)"],
        ["ratings.vgs_on_v", "VGS on (V)"],
        ["ratings.vgs_off_v", "VGS off (V)"],
        ["static.vgs_th_v.25", "VGS(th) 25C (V)"],
        ["static.rds_on_mohm.25", "RDS(on) 25C (mΩ)"],
        ["static.gfs_s", "gfs (S)"],
        ["static.rg_int_ohm", "RG int (Ω)"],
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
      if (!curve) { document.getElementById("curveBox").innerHTML = `<div class="status warn">未识别到可自动数字化的 Ciss/Coss/Crss 矢量曲线。</div>`; return; }
      const data = curve.data || {};
      const rows = (data.vds_v || []).map((v, i) => `
        <tr><td>${v}</td><td>${data.ciss_pf[i]}</td><td>${data.coss_pf[i]}</td><td>${data.crss_pf[i]}</td></tr>
      `).join("");
      document.getElementById("curveBox").innerHTML = `
        <div><span class="pill">page ${curve.page}</span><span class="pill">confidence ${Math.round(curve.confidence * 100)}%</span></div>
        <table><thead><tr><th>VDS</th><th>Ciss</th><th>Coss</th><th>Crss</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }
    function renderTables(tables) {
      if (!tables.length) { document.getElementById("tablesBox").textContent = "未识别到表格候选。"; return; }
      document.getElementById("tablesBox").innerHTML = tables.slice(0, 4).map(table => `
        <div class="status"><b>page ${table.page}</b> score ${Math.round(table.score * 100)}%</div>
        <table><tbody>${table.rows.slice(0, 6).map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>
      `).join("");
    }
    function renderEvaluation(evaluation, fits) {
      if (!evaluation) { document.getElementById("evaluation").textContent = ""; return; }
      const fitRows = (fits || []).map(f => `<tr><td>${escapeHtml(f.model)}</td><td class="mono">${escapeHtml(JSON.stringify(f.parameters))}</td></tr>`).join("");
      document.getElementById("evaluation").innerHTML = `
        <div class="status"><b>质量评分 ${evaluation.overall_score}/100</b>，等级 ${escapeHtml(evaluation.grade)}</div>
        <div>${Object.entries(evaluation.scores || {}).map(([k,v]) => `<span class="pill">${escapeHtml(k)} ${Math.round(v * 100)}%</span>`).join("")}</div>
        <div>${(evaluation.notes || []).map(n => `<div class="status warn">${escapeHtml(n)}</div>`).join("")}</div>
        <table><thead><tr><th>模型</th><th>拟合参数</th></tr></thead><tbody>${fitRows}</tbody></table>
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
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
  </script>
</body>
</html>
"""
