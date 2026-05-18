import { createWorkbenchBackend, formatRuntimeBadge } from "./workbench_runtime.js";
import { WorkbenchModuleRegistry } from "./module_contracts.js";
import { DEMO_PROJECT, DIODE_DEMO_PROJECT, PDF_EXTRACTOR_MODULE } from "./pdf_extractors.js";
import { MODEL_EMITTER_MODULE } from "./model_emitters.js";
import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.mjs";

let currentProject = null;
let currentFindings = [];
let currentSeries = null;
let currentVariantProjects = [];
let currentSeriesVariants = [];

const backend = createWorkbenchBackend();
const modules = new WorkbenchModuleRegistry([PDF_EXTRACTOR_MODULE, MODEL_EMITTER_MODULE]);
const pdfExtractor = modules.require("browser-pdf-text-extractor");
const modelEmitter = modules.require("browser-spice-starter-emitter");
const $ = id => document.getElementById(id);

initRuntimeBadge();
wireUi();

function initRuntimeBadge() {
  backend.capabilities().then(capabilities => {
    $("runtimeBadge").textContent = formatRuntimeBadge(capabilities);
    $("runtimeBadge").title = capabilities.runtime?.summary || "";
  }).catch(() => {
    $("runtimeBadge").textContent = "Browser Pages Mode / datasheet2spice-api-v1";
  });
}

function wireUi() {
  $("extractPdfBtn").addEventListener("click", onExtractPdf);
  $("jsonFile").addEventListener("change", onLoadJson);
  $("loadDemoBtn").addEventListener("click", onLoadDemo);
  $("generateBtn").addEventListener("click", onGenerateBundle);
  $("seriesPartSelect").addEventListener("change", onSeriesPartChange);
  $("generateAllSeries").addEventListener("change", updateSeriesGenerateState);
  $("componentProfile").addEventListener("change", () => updateModelControls(true));
  updateModelControls(true);
}

async function onExtractPdf() {
  const file = $("pdfFile").files[0];
  if (!file) {
    setStatus("inputStatus", "Please choose a PDF first.", "warn");
    return;
  }
  try {
    setStatus("inputStatus", "Reading PDF in the browser...");
    const text = await pdfExtractor.extractPdfText(pdfjsLib, file);
    const extraction = pdfExtractor.extractProjectFromText(text, file.name, selectedProfile());
    saveProject(extraction.project, extraction.findings, extraction);
    const series = extraction.series;
    const needsChoice = series && series.parts?.length > 1 && !series.has_default;
    setStatus(
      "inputStatus",
      needsChoice
        ? `Detected ${series.parts.length} series parts in ${file.name}. Choose the target part before generation.`
        : `Extracted ${extraction.findings.length} starter fields from ${file.name}. Review the JSON before generation.`,
      needsChoice ? "warn" : ""
    );
  } catch (err) {
    setStatus("inputStatus", `PDF extraction failed: ${err.message}`, "bad");
  }
}

async function onLoadJson() {
  const file = $("jsonFile").files[0];
  if (!file) return;
  try {
    const project = JSON.parse(await file.text());
    saveProject(project, [], null);
    setStatus("inputStatus", `Loaded ${file.name}.`);
  } catch (err) {
    setStatus("inputStatus", `Could not load JSON: ${err.message}`, "bad");
  }
}

function onLoadDemo() {
  const demo = selectedProfile() === "diode.power" ? DIODE_DEMO_PROJECT : DEMO_PROJECT;
  saveProject(structuredClone(demo), [], null);
  setStatus("inputStatus", "Demo project loaded.");
}

async function onGenerateBundle() {
  let project;
  try {
    project = JSON.parse($("projectJson").value);
  } catch (err) {
    setStatus("generateStatus", `Invalid JSON: ${err.message}`, "bad");
    return;
  }
  syncProfileFromProject(project);
  const models = [...document.querySelectorAll("input[name=model]:checked")].map(el => el.value);
  const dialectValue = $("dialect").value;
  const dialects = dialectValue === "all" ? modelEmitter.dialects : [dialectValue];
  if (!models.length) {
    setStatus("generateStatus", "Select at least one model family.", "warn");
    return;
  }
  if (!window.JSZip) {
    setStatus("generateStatus", "ZIP library did not load.", "bad");
    return;
  }
  const generateAll = $("generateAllSeries").checked && currentVariantProjects.length > 1;
  const projects = generateAll ? currentVariantProjects : [project];
  const files = {};
  for (const item of projects) {
    const generated = modelEmitter.generateBundle(item, models, dialects);
    const prefix = generateAll ? `${modelEmitter.modelName(item)}/` : "";
    for (const [name, content] of Object.entries(generated)) files[`${prefix}${name}`] = content;
  }
  if (generateAll) {
    files["series_summary.json"] = JSON.stringify({
      parts: currentVariantProjects.map(item => item.device?.part_number),
      models,
      dialects,
      summary: currentSeries?.summary || null
    }, null, 2) + "\n";
  }
  const zip = new window.JSZip();
  for (const [name, content] of Object.entries(files)) zip.file(name, content);
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const zipName = generateAll ? "series_models.zip" : `${modelEmitter.modelName(project)}_models.zip`;
  $("files").innerHTML = `<a href="${url}" download="${zipName}">Download ${zipName}</a>` +
    Object.keys(files).sort().map(name => `<span class="mono">${escapeHtml(name)}</span>`).join("");
  $("report").textContent = generateAll ? `Generated ${projects.length} part folders.` : files[`${modelEmitter.modelName(project)}_README.txt`];
  setStatus("generateStatus", `Generated ${Object.keys(files).length} files.`);
}

function saveProject(project, findings = [], extraction = null) {
  currentProject = project;
  currentFindings = findings;
  if (extraction) {
    currentSeries = extraction.series || null;
    currentVariantProjects = extraction.variant_projects || [];
    currentSeriesVariants = extraction.series_variants || [];
  } else {
    currentSeries = null;
    currentVariantProjects = [];
    currentSeriesVariants = [];
  }
  syncProfileFromProject(project);
  $("projectJson").value = JSON.stringify(project, null, 2);
  $("generateBtn").disabled = false;
  renderFindings(currentFindings);
  renderSeriesSelector();
}

function selectedProfile() {
  return $("componentProfile").value || "mosfet.power";
}

function syncProfileFromProject(project) {
  const profile = project?.component?.profile;
  if (profile && [...$("componentProfile").options].some(option => option.value === profile)) {
    $("componentProfile").value = profile;
  }
  updateModelControls(true);
}

function updateModelControls(resetChecks = false) {
  const profile = selectedProfile();
  document.querySelectorAll("[data-model-profile]").forEach(label => {
    const input = label.querySelector("input[name=model]");
    const visible = label.dataset.modelProfile === profile;
    label.hidden = !visible;
    if (resetChecks && input) input.checked = visible;
  });
}

function renderSeriesSelector() {
  const series = currentSeries;
  if (!series || !series.parts || series.parts.length <= 1) {
    $("seriesBox").hidden = true;
    $("generateAllSeries").checked = false;
    return;
  }
  $("seriesBox").hidden = false;
  const needsChoice = !series.has_default;
  $("seriesStatus").textContent = needsChoice
    ? `Series datasheet detected: ${series.parts.join(", ")}. No filename match was found.`
    : `Series datasheet detected: ${series.parts.join(", ")}. Default part: ${series.default_part}.`;
  $("seriesStatus").className = "status" + (needsChoice ? " warn" : "");
  $("seriesPartSelect").innerHTML =
    (needsChoice ? '<option value="">Choose a part...</option>' : "") +
    series.parts.map(part => `<option value="${escapeHtml(part)}">${escapeHtml(part)}</option>`).join("");
  $("seriesPartSelect").value = needsChoice ? "" : series.selected_part;
  updateSeriesGenerateState();
}

function onSeriesPartChange() {
  const part = $("seriesPartSelect").value;
  if (!part) {
    updateSeriesGenerateState();
    return;
  }
  const project = currentVariantProjects.find(item => item.device?.part_number === part);
  if (!project) return;
  currentProject = project;
  if (currentSeries) currentSeries.selected_part = part;
  const variant = currentSeriesVariants.find(item => item.part_number === part);
  if (variant?.findings) {
    currentFindings = variant.findings;
    renderFindings(currentFindings);
  }
  $("projectJson").value = JSON.stringify(project, null, 2);
  $("generateBtn").disabled = false;
  setStatus("inputStatus", `Selected ${part}. Review the JSON before generation.`);
}

function updateSeriesGenerateState() {
  if (!currentProject) {
    $("generateBtn").disabled = true;
    return;
  }
  const needsChoice = currentSeries && currentSeries.parts?.length > 1 && !currentSeries.has_default && !$("seriesPartSelect").value;
  const generateAll = $("generateAllSeries").checked && currentVariantProjects.length > 1;
  $("generateBtn").disabled = Boolean(needsChoice && !generateAll);
  if (needsChoice && generateAll) setStatus("inputStatus", "All detected series parts will be generated.");
}

function renderFindings(findings) {
  if (!findings.length) {
    $("findings").innerHTML = '<div class="status warn">No extracted fields to show.</div>';
    return;
  }
  $("findings").innerHTML = `
    <table><thead><tr><th>Field</th><th>Value</th><th>Confidence</th></tr></thead><tbody>
    ${findings.map(f => `<tr><td class="mono">${escapeHtml(f.field)}</td><td class="mono">${escapeHtml(f.value)}</td><td>${Math.round(f.confidence * 100)}%</td></tr>`).join("")}
    </tbody></table>`;
}

function setStatus(id, text, kind = "") {
  const el = $(id);
  el.className = "status" + (kind ? " " + kind : "");
  el.textContent = text;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
