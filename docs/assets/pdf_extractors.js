export const DEMO_PROJECT = {
  schema_version: "1.0",
  component: {
    family: "mosfet",
    profile: "mosfet.power"
  },
  device: {
    part_number: "DEMO_SIC_1200",
    vendor: "Demo",
    type: "SiC MOSFET",
    package: "TO-247",
    datasheet: "browser-demo"
  },
  ratings: { vdss_v: 1200, id_cont_a: 130, vgs_on_v: 18, vgs_off_v: -2 },
  static: {
    vgs_th_v: { "25": 3.8, "175": 3.0 },
    rds_on_mohm: { "25": 11, "175": 25.9 },
    gfs_s: 47,
    rg_int_ohm: 1
  },
  dynamic: {
    capacitance: {
      vds_v: [0.1, 1, 10, 100, 800, 1000],
      ciss_pf: [9240, 9036, 7917, 7901, 7870, 7865],
      coss_pf: [21113, 790, 2155, 539, 209, 209],
      crss_pf: [2201, 1899, 219, 29, 9.5, 9.5]
    },
    gate_charge: { qg_nc: 307, qgs_nc: 101, qgd_nc: 45 },
    channel_fit: { idsat_reference_a: 130, vgs_reference_v: 18 },
    body_diode: { vsd_25c_typ_v: 3.8, trr_ns: 19, qrr_nc: 876, irrm_a: 74 }
  },
  parasitics: { ld_nh: 2, ls_nh: 1, lg_nh: 0.2, rg_ext_ohm: 4.7 },
  models: {},
  provenance: []
};

export const DIODE_DEMO_PROJECT = {
  schema_version: "1.0",
  component: {
    family: "diode",
    profile: "diode.power"
  },
  device: {
    part_number: "DEMO_DIODE_650",
    vendor: "Demo",
    type: "SiC Schottky Diode",
    package: "TO-247",
    datasheet: "browser-demo"
  },
  ratings: { vrrm_v: 650, if_av_a: 20, ifsm_a: 180 },
  static: {
    forward_voltage: { vf_v: 1.7, if_a: 20 },
    leakage: { ir_ua: 50 }
  },
  dynamic: {
    junction_capacitance: { cj0_pf: 120 },
    reverse_recovery: { trr_ns: 12, qrr_nc: 0 }
  },
  thermal: { rth_jc_c_per_w: 1.2 },
  parasitics: { la_nh: 1.2, lk_nh: 1.0, ra_ohm: 0.002, rk_ohm: 0.002 },
  models: {},
  provenance: []
};

export const PDF_EXTRACTOR_MODULE = {
  id: "browser-pdf-text-extractor",
  kind: "extractor",
  label: "Browser PDF Text Extractor",
  version: "0.1.0",
  description: "Starter project heuristics used when a trusted local PDF parser is supplied.",
  component_profiles: ["mosfet.power", "diode.power"],
  runtime_modes: ["browser-pages"],
  capabilities: ["extract_pdf_text", "extract_project_from_text", "extract_mosfet_from_text", "extract_diode_from_text"],
  extractPdfText,
  extractProjectFromText
};

export async function extractPdfText(pdfjsLib, file, maxPagesToRead = 16) {
  const data = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data }).promise;
  const chunks = [];
  const maxPages = Math.min(pdf.numPages, maxPagesToRead);
  for (let pageNumber = 1; pageNumber <= maxPages; pageNumber += 1) {
    const page = await pdf.getPage(pageNumber);
    const textContent = await page.getTextContent();
    chunks.push(textContent.items.map(item => item.str || "").join(" "));
  }
  return chunks.join("\n");
}

export function extractProjectFromText(text, filename, componentProfile = "mosfet.power") {
  if (componentProfile === "diode.power") return extractDiodeProjectFromText(text, filename);
  return extractMosfetProjectFromText(text, filename);
}

export function extractMosfetProjectFromText(text, filename) {
  const normalized = text.replace(/\s+/g, " ");
  const findings = [];
  const find = (field, patterns, unit = "", confidence = 0.65) => {
    for (const pattern of patterns) {
      const match = normalized.match(pattern);
      if (match) {
        const value = Number(String(match[1]).replace(",", ""));
        if (Number.isFinite(value)) {
          findings.push({ field, value: `${value}${unit ? " " + unit : ""}`, confidence });
          return value;
        }
      }
    }
    return undefined;
  };

  const partMatch = normalized.match(/\b([A-Z]{1,6}[-_ ]?[A-Z0-9]{3,}[-_.A-Z0-9]*)\b/);
  const part = cleanName(partMatch?.[1] || filename.replace(/\.[^.]+$/, ""));
  const vdss = find("ratings.vdss_v", [/VDSS[^0-9]{0,40}([0-9]{3,4})\s*V/i, /Drain\s*[- ]\s*source voltage[^0-9]{0,80}([0-9]{3,4})\s*V/i], "V", 0.72) ?? 1200;
  const id = find("ratings.id_cont_a", [/\bID\b[^0-9]{0,80}([0-9]{2,4})\s*A/i, /continuous drain[^0-9]{0,80}([0-9]{2,4})\s*A/i], "A", 0.6) ?? 50;
  const vgsOn = find("ratings.vgs_on_v", [/VGS[_ -]?on[^+\-0-9]{0,30}\+?([0-9]{1,2})\s*V/i, /turn[- ]on gate[^+\-0-9]{0,80}\+?([0-9]{1,2})\s*V/i], "V", 0.62) ?? 10;
  const vgsOffRaw = normalized.match(/VGS[_ -]?off[^+\-0-9]{0,30}(-[0-9]{1,2})\s*V/i) || normalized.match(/turn[- ]off gate[^+\-0-9]{0,80}(-[0-9]{1,2})\s*V/i);
  const vgsOff = vgsOffRaw ? Number(vgsOffRaw[1]) : 0;
  if (vgsOffRaw) findings.push({ field: "ratings.vgs_off_v", value: `${vgsOff} V`, confidence: 0.62 });

  const rds = find("static.rds_on_mohm.25", [/RDS\(on\)[^0-9]{0,100}([0-9.]{1,5})\s*m/i, /on[- ]resistance[^0-9]{0,100}([0-9.]{1,5})\s*m/i], "mOhm", 0.58) ?? 20;
  const vth = find("static.vgs_th_v.25", [/VGS\(th\)[^0-9]{0,100}([0-9.]{1,4})\s*V/i, /threshold voltage[^0-9]{0,100}([0-9.]{1,4})\s*V/i], "V", 0.58) ?? 4;
  const gfs = find("static.gfs_s", [/\bgfs\b[^0-9]{0,80}([0-9.]{1,4})\s*S/i, /transconductance[^0-9]{0,80}([0-9.]{1,4})\s*S/i], "S", 0.58) ?? 20;
  const rg = find("static.rg_int_ohm", [/\bRG\b[^0-9]{0,80}([0-9.]{1,4})\s*(?:ohm|Ohm|\u03a9)/i, /gate input resistance[^0-9]{0,80}([0-9.]{1,4})/i], "Ohm", 0.52) ?? 1;
  const ciss = find("dynamic.capacitance.ciss_pf", [/\bCiss\b[^0-9]{0,80}([0-9.]{2,8})\s*pF/i, /input capacitance[^0-9]{0,80}([0-9.]{2,8})\s*pF/i], "pF", 0.6) ?? 2000;
  const coss = find("dynamic.capacitance.coss_pf", [/\bCoss\b[^0-9]{0,80}([0-9.]{2,8})\s*pF/i, /output capacitance[^0-9]{0,80}([0-9.]{2,8})\s*pF/i], "pF", 0.6) ?? 300;
  const crss = find("dynamic.capacitance.crss_pf", [/\bCrss\b[^0-9]{0,80}([0-9.]{1,8})\s*pF/i, /reverse transfer capacitance[^0-9]{0,80}([0-9.]{1,8})\s*pF/i], "pF", 0.6) ?? 30;
  const qg = find("dynamic.gate_charge.qg_nc", [/\bQg\b[^0-9]{0,80}([0-9.]{1,6})\s*nC/i, /total gate charge[^0-9]{0,80}([0-9.]{1,6})\s*nC/i], "nC", 0.55) ?? 100;
  const qgs = find("dynamic.gate_charge.qgs_nc", [/\bQgs\b[^0-9]{0,80}([0-9.]{1,6})\s*nC/i], "nC", 0.5) ?? Math.round(qg * 0.3);
  const qgd = find("dynamic.gate_charge.qgd_nc", [/\bQgd\b[^0-9]{0,80}([0-9.]{1,6})\s*nC/i], "nC", 0.5) ?? Math.round(qg * 0.2);
  const trr = find("dynamic.body_diode.trr_ns", [/\btrr\b[^0-9]{0,80}([0-9.]{1,6})\s*ns/i, /reverse recovery time[^0-9]{0,80}([0-9.]{1,6})\s*ns/i], "ns", 0.5) ?? 30;
  const qrr = find("dynamic.body_diode.qrr_nc", [/\bQrr\b[^0-9]{0,80}([0-9.]{1,8})\s*nC/i, /reverse recovery charge[^0-9]{0,80}([0-9.]{1,8})\s*nC/i], "nC", 0.5) ?? 0;
  const irrm = find("dynamic.body_diode.irrm_a", [/\bIrrm\b[^0-9]{0,80}([0-9.]{1,6})\s*A/i, /peak reverse recovery current[^0-9]{0,80}([0-9.]{1,6})\s*A/i], "A", 0.5) ?? 0;
  const cHi = Math.max(ciss, coss, crss);

  const project = structuredClone(DEMO_PROJECT);
  project.device.part_number = part;
  project.device.datasheet = filename;
  project.ratings = { vdss_v: vdss, id_cont_a: id, vgs_on_v: vgsOn, vgs_off_v: vgsOff };
  project.static = {
    vgs_th_v: { "25": vth },
    rds_on_mohm: { "25": rds },
    gfs_s: gfs,
    rg_int_ohm: rg
  };
  project.dynamic.capacitance = {
    vds_v: [0.1, 1, 10, 100, Math.max(vdss * 0.67, 100)],
    ciss_pf: [cHi * 1.2, cHi * 1.1, ciss, ciss * 0.98, ciss * 0.97].map(round3),
    coss_pf: [Math.max(coss * 5, crss * 2), coss * 3, coss * 1.4, coss * 1.05, coss].map(round3),
    crss_pf: [Math.max(crss * 8, 1), crss * 3, crss * 1.4, crss * 1.05, crss].map(round3)
  };
  project.dynamic.gate_charge = { qg_nc: qg, qgs_nc: qgs, qgd_nc: qgd };
  project.dynamic.channel_fit = { idsat_reference_a: id, vgs_reference_v: vgsOn };
  project.dynamic.body_diode = { trr_ns: trr, qrr_nc: qrr, irrm_a: irrm };
  project.provenance = [{ source: filename, kind: "browser_pdf_text", note: "Extracted with browser-side PDF.js heuristics. Review all values before use." }];
  return { project, findings };
}

export function extractDiodeProjectFromText(text, filename, selectedPart = null) {
  const normalized = text.replace(/\s+/g, " ");
  const findings = [];
  const seriesParts = seriesCandidates(normalized);
  const defaultPart = defaultPartFromFilename(filename, seriesParts);
  const targetPart = selectedPart || defaultPart || seriesParts[0] || cleanName(filename.replace(/\.[^.]+$/, ""));
  const find = (field, patterns, unit = "", confidence = 0.62) => {
    for (const pattern of patterns) {
      const match = normalized.match(pattern);
      if (match) {
        const value = Number(String(match[1]).replace(",", ""));
        if (Number.isFinite(value)) {
          findings.push({ field, value: `${value}${unit ? " " + unit : ""}`, confidence });
          return value;
        }
      }
    }
    return undefined;
  };
  const findSeries = (field, markers, unit = "", confidence = 0.68, scale = 1) => {
    for (const marker of markers) {
      const markerIndex = markerIndexOf(normalized, marker);
      if (markerIndex < 0) continue;
      const snippet = normalized.slice(markerIndex, markerIndex + 180);
      const values = numericTokens(snippet);
      if (!values.length) continue;
      const targetIndex = seriesParts.indexOf(targetPart);
      const picked = targetIndex >= 0 && seriesParts.length > 1 && values.length >= seriesParts.length
        ? values[targetIndex]
        : values[values.length - 1];
      const value = round3(picked * scale);
      findings.push({ field, value: `${value}${unit ? " " + unit : ""}`, confidence });
      return value;
    }
    return undefined;
  };
  const findScaled = (field, patterns, sourceUnit, outputUnit, scale, confidence = 0.58) => {
    const value = find(field, patterns, sourceUnit, confidence);
    if (value === undefined) return undefined;
    const scaled = round3(value * scale);
    const existing = findings.find(item => item.field === field);
    if (existing) existing.value = `${scaled}${outputUnit ? " " + outputUnit : ""}`;
    return scaled;
  };

  const part = targetPart || cleanName(filename.replace(/\.[^.]+$/, ""));
  const vrrm = findSeries("ratings.vrrm_v", ["VRRM", "Maximum Repetitive Peak Reverse Voltage"], "V", 0.78) ?? find("ratings.vrrm_v", [
    /\bVRRM\b[^0-9]{0,80}([0-9]{2,5})\s*V/i,
    /repetitive peak reverse voltage[^0-9]{0,120}([0-9]{2,5})\s*V/i,
    /reverse voltage[^0-9]{0,100}([0-9]{2,5})\s*V/i
  ], "V", 0.72) ?? 600;
  const ifAv = find("ratings.if_av_a", [
    /\bIF\(AV\)\s*A\s*([0-9.]{1,5})/i,
    /\bIF\(AV\)[^0-9]{0,80}([0-9.]{1,5})\s*A/i,
    /\bIFAV\b[^0-9]{0,80}([0-9.]{1,5})\s*A/i,
    /average forward current[^0-9]{0,120}([0-9.]{1,5})\s*A/i
  ], "A", 0.68) ?? 10;
  const ifsm = find("ratings.ifsm_a", [
    /\bIFSM\b\s*A\s*([0-9.]{1,6})/i,
    /\bIFSM\b[^0-9]{0,100}([0-9.]{1,6})\s*A/i,
    /surge forward current[^0-9]{0,120}([0-9.]{1,6})\s*A/i
  ], "A", 0.58) ?? Math.round(ifAv * 8);
  const vf = findSeries("static.forward_voltage.vf_v", ["VF1", "IF=1.0A", "Maximum instantaneous forward voltage"], "V", 0.76) ?? find("static.forward_voltage.vf_v", [
    /\bVF\b[^0-9]{0,100}([0-9.]{1,5})\s*V/i,
    /forward voltage[^0-9]{0,120}([0-9.]{1,5})\s*V/i
  ], "V", 0.62) ?? 1.2;
  const ir = find("static.leakage.ir_ua", [
    /\bIR\b[^0-9]{0,100}([0-9.]{1,8})\s*uA/i,
    /reverse current[^0-9]{0,120}([0-9.]{1,8})\s*uA/i,
    /leakage current[^0-9]{0,120}([0-9.]{1,8})\s*uA/i
  ], "uA", 0.52) ?? findScaled("static.leakage.ir_ua", [
    /\bIR1\b\s*mA\s*([0-9.]{1,8})/i,
    /reverse current[^0-9]{0,120}([0-9.]{1,8})\s*mA/i
  ], "mA", "uA", 1000, 0.58) ?? 10;
  const cj = find("dynamic.junction_capacitance.cj0_pf", [
    /\bCJ\b\s*pF\s*([0-9.]{1,8})/i,
    /\bCj\b[^0-9]{0,100}([0-9.]{1,8})\s*pF/i,
    /\bCt\b[^0-9]{0,100}([0-9.]{1,8})\s*pF/i,
    /junction capacitance[^0-9]{0,120}\bCJ\b\s*pF\s*([0-9.]{1,8})/i,
    /junction capacitance[^0-9]{0,120}([0-9.]{1,8})\s*pF/i,
    /total capacitance[^0-9]{0,120}([0-9.]{1,8})\s*pF/i
  ], "pF", 0.58) ?? 80;
  const trr = find("dynamic.reverse_recovery.trr_ns", [
    /\btrr\b[^0-9]{0,100}([0-9.]{1,8})\s*ns/i,
    /reverse recovery time[^0-9]{0,120}([0-9.]{1,8})\s*ns/i
  ], "ns", 0.52) ?? 20;
  const qrr = find("dynamic.reverse_recovery.qrr_nc", [
    /\bQrr\b[^0-9]{0,100}([0-9.]{1,8})\s*nC/i,
    /reverse recovery charge[^0-9]{0,120}([0-9.]{1,8})\s*nC/i
  ], "nC", 0.52) ?? 0;
  const rth = find("thermal.rth_jc_c_per_w", [
    /\bRth\(j[- ]?c\)\b[^0-9]{0,100}([0-9.]{1,5})/i,
    /thermal resistance[^0-9]{0,120}([0-9.]{1,5})/i
  ], "C/W", 0.45) ?? 1.5;

  const project = structuredClone(DIODE_DEMO_PROJECT);
  project.device.part_number = part;
  project.device.type = /\bSiC\b/i.test(normalized) ? "sic_schottky_diode" : /Schottky/i.test(normalized) ? "schottky_diode" : "power_diode";
  project.device.datasheet = filename;
  if (seriesParts.length) project.device.series_parts = seriesParts;
  project.ratings = { vrrm_v: vrrm, if_av_a: ifAv, ifsm_a: ifsm };
  project.static = {
    forward_voltage: { vf_v: vf, if_a: ifAv },
    leakage: { ir_ua: ir }
  };
  project.dynamic = {
    junction_capacitance: { cj0_pf: cj },
    reverse_recovery: { trr_ns: trr, qrr_nc: qrr }
  };
  project.thermal = { rth_jc_c_per_w: rth };
  project.provenance = [{ source: filename, kind: "browser_pdf_text", note: "Extracted with browser-side PDF.js diode heuristics. Review all values before use." }];
  const variantResults = selectedPart || seriesParts.length <= 1
    ? []
    : seriesParts.map(partNumber => extractDiodeProjectFromText(text, filename, partNumber));
  const variantProjects = variantResults.map(result => result.project);
  const seriesVariants = variantResults.map((result, index) => ({
    part_number: seriesParts[index],
    project: result.project,
    findings: result.findings,
    warnings: [],
    is_default: seriesParts[index] === defaultPart
  }));
  const series = seriesParts.length
    ? {
        parts: seriesParts,
        default_part: defaultPart,
        selected_part: part,
        has_default: Boolean(defaultPart),
        summary: summarizeSeriesProjects(variantProjects.length ? variantProjects : [project])
      }
    : null;
  return { project, findings, series, variant_projects: variantProjects, series_variants: seriesVariants };
}

function defaultPartFromFilename(filename, seriesParts) {
  const fileStem = cleanName(String(filename || "").replace(/\.[^.]+$/, ""));
  const fileParts = looseSeriesCandidates(fileStem);
  if (fileParts.length === 1 && (!seriesParts.length || seriesParts.includes(fileParts[0]))) return fileParts[0];
  if (seriesParts.includes(fileStem)) return fileStem;
  return null;
}

function seriesCandidates(text) {
  const parameterIndex = String(text || "").toLowerCase().indexOf("parameter");
  if (parameterIndex >= 0) {
    const headerParts = looseSeriesCandidates(String(text).slice(parameterIndex, parameterIndex + 240));
    if (headerParts.length > 1) return headerParts;
  }
  return looseSeriesCandidates(text);
}

function looseSeriesCandidates(text) {
  const matches = String(text || "").match(/\b(?:[A-Z]{1,6}\d{2,6}[A-Z0-9]{0,8}|\dN\d{3,5}[A-Z0-9]*)\b/gi) || [];
  const seen = new Set();
  const result = [];
  for (const match of matches) {
    const cleaned = cleanName(match);
    if (!cleaned || cleaned.endsWith("REF") || seen.has(cleaned)) continue;
    seen.add(cleaned);
    result.push(cleaned);
  }
  return result;
}

function markerIndexOf(text, marker) {
  const exact = text.indexOf(marker);
  if (exact >= 0) return exact;
  return text.toLowerCase().indexOf(String(marker).toLowerCase());
}

function numericTokens(text) {
  const matches = String(text || "").match(/(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?![A-Za-z])/g) || [];
  return matches.map(Number).filter(Number.isFinite);
}

function summarizeSeriesProjects(projects) {
  const paths = [
    "ratings.vrrm_v",
    "ratings.if_av_a",
    "ratings.ifsm_a",
    "static.forward_voltage.vf_v",
    "static.leakage.ir_ua",
    "dynamic.junction_capacitance.cj0_pf",
    "thermal.rth_jc_c_per_w"
  ];
  const common = {};
  const varying = {};
  for (const path of paths) {
    const values = Object.fromEntries(projects.map(project => [project.device?.part_number || "DEVICE", getObjectPath(project, path)]));
    const unique = new Set(Object.values(values).map(value => JSON.stringify(value)));
    if (unique.size === 1) common[path] = Object.values(values)[0];
    else varying[path] = values;
  }
  return { common, varying };
}

function getObjectPath(obj, path) {
  return path.split(".").reduce((cur, key) => cur && cur[key] !== undefined ? cur[key] : undefined, obj);
}

function cleanName(text) {
  return String(text || "DEVICE").toUpperCase().replace(/[^A-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "DEVICE";
}

function round3(value) {
  return Math.round(Number(value) * 1000) / 1000;
}
