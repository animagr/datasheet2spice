import unittest

from datasheet2spice.contracts import API_CONTRACT, MODULE_CONTRACT, ModuleManifest, service_contract, validate_module_manifest
from datasheet2spice.plugins import module_catalog
from datasheet2spice.service import backend_capabilities


class ContractTests(unittest.TestCase):
    def test_module_manifest_validates_and_serializes(self):
        manifest = ModuleManifest(
            id="example.extractor",
            kind="extractor",
            label="Example Extractor",
            component_profiles=("mosfet.power",),
            runtime_modes=("browser-pages",),
            capabilities=("extract",),
        )
        data = manifest.to_dict()
        self.assertEqual(data["contract"], MODULE_CONTRACT)
        self.assertEqual(data["id"], "example.extractor")

    def test_module_manifest_rejects_bad_id(self):
        with self.assertRaises(ValueError):
            validate_module_manifest(
                {
                    "contract": MODULE_CONTRACT,
                    "id": "Bad ID",
                    "kind": "extractor",
                    "label": "Bad",
                    "version": "0.1.0",
                    "runtime_modes": [],
                    "capabilities": [],
                }
            )

    def test_service_contract_lists_core_operations(self):
        contract = service_contract()
        self.assertEqual(contract["contract"], API_CONTRACT)
        names = {operation["name"] for operation in contract["operations"]}
        self.assertIn("extractPdf", names)
        self.assertIn("emitModelBundle", names)
        self.assertIn("digitizeCurve", names)

    def test_backend_capabilities_include_modules(self):
        capabilities = backend_capabilities()
        self.assertEqual(capabilities["contract"], API_CONTRACT)
        self.assertIn("service_contract", capabilities)
        module_ids = {module["id"] for module in capabilities["module_catalog"]["modules"]}
        self.assertIn("mosfet.power", module_ids)
        self.assertIn("diode.power", module_ids)
        self.assertIn("abm-basic", module_ids)
        self.assertIn("diode-basic", module_ids)
        self.assertIn("vdmos-static-fast", module_ids)

    def test_module_catalog_is_json_ready(self):
        catalog = module_catalog(include_entrypoints=False)
        self.assertEqual(catalog["contract"], MODULE_CONTRACT)
        self.assertTrue(all("capabilities" in module for module in catalog["modules"]))


if __name__ == "__main__":
    unittest.main()
