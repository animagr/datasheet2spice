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

from .extractors.pdf_mosfet import extract_mosfet_project_from_pdf
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

    zip_path = out / f"{project.model_name}_models.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            zf.write(item["path"], arcname=item["name"])
    files.append({"name": zip_path.name, "path": str(zip_path), "content": ""})
    session = out.parent.name
    return {"ok": True, "errors": [], "files": files, "download_url": f"/download/{session}/{zip_path.name}", "report": report}


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
        <button id="generateBtn" disabled>生成模型文件</button>
        <div id="generateStatus" class="status">提取成功后可生成。</div>
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
      setStatus("extractStatus", `已提取 ${data.project.device.part_number}，请检查右侧 JSON。`);
      document.getElementById("warnings").innerHTML = (data.warnings || []).map(w => `<div class="status warn">${escapeHtml(w)}</div>`).join("");
      document.getElementById("findings").innerHTML = (data.findings || []).map(f => `
        <tr>
          <td class="mono">${escapeHtml(f.field)}</td>
          <td class="mono">${escapeHtml(JSON.stringify(f.value))} ${escapeHtml(f.unit || "")}</td>
          <td>${Math.round((f.confidence || 0) * 100)}%</td>
          <td>${escapeHtml(f.snippet || "")}</td>
        </tr>`).join("");
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
      document.getElementById("files").innerHTML = `<a href="${data.download_url}">下载 ZIP 模型包</a><br>` +
        data.files.map(f => `<span class="mono">${escapeHtml(f.name)}</span>`).join("<br>");
      document.getElementById("report").textContent = data.report || "";
    });
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
  </script>
</body>
</html>
"""
