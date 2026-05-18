export const API_CONTRACT = "datasheet2spice-api-v1";

export const RUNTIME_MODES = {
  browserPages: {
    name: "browser-pages",
    label: "Static Browser Mode",
    deployment: "Static browser files",
    summary: "No-install project review and starter model export without remote code loading.",
    features: [
      "manual_review",
      "starter_model_generation",
      "individual_file_download"
    ],
    limitations: [
      "pdf_extraction_requires_local_python",
      "no_local_simulator_execution",
      "limited_scanned_pdf_ocr",
      "no_server_side_file_storage"
    ]
  },
  localPython: {
    name: "local-python",
    label: "Local Python Backend",
    deployment: "User workstation",
    summary: "High-fidelity extraction, PDF evidence, digitization, fitting, and simulator adapters.",
    features: [
      "pymupdf_text_extraction",
      "pdf_evidence_screenshots",
      "table_candidate_recognition",
      "vector_curve_digitization",
      "raster_curve_digitization",
      "parameter_fitting",
      "model_quality_evaluation",
      "optional_simulator_smoke_tests"
    ],
    limitations: [
      "requires_local_install",
      "optional_dependencies_have_their_own_licenses"
    ]
  }
};

export function runtimeModeFromLocation(locationLike = window.location) {
  const url = new URL(locationLike.href);
  const requested = url.searchParams.get("backend") || url.searchParams.get("runtime");
  if (requested === "local" || requested === "local-python") return "local-python";
  return "browser-pages";
}

export class BrowserPagesBackend {
  constructor(options = {}) {
    this.mode = "browser-pages";
    this.options = options;
  }

  async capabilities() {
    return {
      active_mode: this.mode,
      contract: API_CONTRACT,
      available_modes: ["browser-pages"],
      runtime: RUNTIME_MODES.browserPages
    };
  }
}

export class LocalPythonBackend {
  constructor(options = {}) {
    this.mode = "local-python";
    this.baseUrl = localOnlyBaseUrl(options.baseUrl || "");
  }

  async capabilities() {
    const response = await fetch(`${this.baseUrl}/api/capabilities`);
    if (!response.ok) throw new Error(`capabilities request failed: ${response.status}`);
    return response.json();
  }

  async extractPdf(file, session) {
    const form = new FormData();
    form.append("pdf", file);
    if (session) form.append("session", session);
    const response = await fetch(`${this.baseUrl}/api/extract`, {
      method: "POST",
      body: form
    });
    if (!response.ok) throw new Error(`extract request failed: ${response.status}`);
    return response.json();
  }

  async fitModel(project) {
    return postJson(`${this.baseUrl}/api/fit`, { project });
  }

  async emitModelBundle(project, models, dialects, session) {
    return postJson(`${this.baseUrl}/api/generate`, { project, models, dialects, session });
  }
}

export function createWorkbenchBackend(options = {}) {
  const mode = options.mode || runtimeModeFromLocation(options.location || window.location);
  if (mode === "local-python") return new LocalPythonBackend(options);
  return new BrowserPagesBackend(options);
}

export function formatRuntimeBadge(capabilities) {
  const runtime = capabilities?.runtime || {};
  const label = runtime.label || capabilities?.active_mode || "Unknown Runtime";
  const contract = capabilities?.contract || API_CONTRACT;
  return `${label} / ${contract}`;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `request failed: ${response.status}`);
  return data;
}

function localOnlyBaseUrl(baseUrl) {
  if (!baseUrl) return "";
  const parsed = new URL(baseUrl, window.location.href);
  if (parsed.origin !== window.location.origin) {
    throw new Error("local-python backend must use the same origin as the workbench");
  }
  return parsed.pathname.replace(/\/$/, "");
}
