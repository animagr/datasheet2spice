export const MODULE_CONTRACT = "datasheet2spice-module-v1";

export class WorkbenchModuleRegistry {
  constructor(modules = []) {
    this.modules = new Map();
    for (const module of modules) this.register(module);
  }

  register(module) {
    validateWorkbenchModule(module);
    if (this.modules.has(module.id)) {
      throw new Error(`duplicate module id: ${module.id}`);
    }
    this.modules.set(module.id, module);
    return module;
  }

  get(id) {
    return this.modules.get(id) || null;
  }

  require(id) {
    const module = this.get(id);
    if (!module) throw new Error(`module is not registered: ${id}`);
    return module;
  }

  byKind(kind) {
    return [...this.modules.values()].filter(module => module.kind === kind);
  }

  manifests() {
    return [...this.modules.values()].map(module => manifestOf(module));
  }
}

export function validateWorkbenchModule(module) {
  const manifest = manifestOf(module);
  const required = ["contract", "id", "kind", "label", "version", "runtime_modes", "capabilities"];
  for (const key of required) {
    if (manifest[key] === undefined || manifest[key] === null) {
      throw new Error(`module manifest missing required field: ${key}`);
    }
  }
  if (manifest.contract !== MODULE_CONTRACT) {
    throw new Error(`unsupported module contract: ${manifest.contract}`);
  }
  if (!/^[a-z0-9][a-z0-9_.-]{1,80}$/.test(manifest.id)) {
    throw new Error(`invalid module id: ${manifest.id}`);
  }
  if (!Array.isArray(manifest.runtime_modes) || !Array.isArray(manifest.capabilities)) {
    throw new Error("runtime_modes and capabilities must be arrays");
  }
  return true;
}

export function manifestOf(module) {
  const manifest = module.manifest || module;
  return {
    contract: manifest.contract || MODULE_CONTRACT,
    id: manifest.id || module.id,
    kind: manifest.kind || module.kind,
    label: manifest.label || module.label,
    version: manifest.version || "0.1.0",
    description: manifest.description || "",
    component_profiles: [...(manifest.component_profiles || [])],
    runtime_modes: [...(manifest.runtime_modes || ["browser-pages"])],
    capabilities: [...(manifest.capabilities || [])],
    dependencies: [...(manifest.dependencies || [])]
  };
}
