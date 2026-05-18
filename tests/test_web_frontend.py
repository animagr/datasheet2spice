from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebFrontendTests(unittest.TestCase):
    def test_frontend_source_matches_pages_copy(self):
        pairs = [
            ("web/workbench_app.html", "docs/workbench_app.html"),
            ("web/assets/workbench_runtime.js", "docs/assets/workbench_runtime.js"),
            ("web/assets/workbench_app.js", "docs/assets/workbench_app.js"),
            ("web/assets/module_contracts.js", "docs/assets/module_contracts.js"),
            ("web/assets/pdf_extractors.js", "docs/assets/pdf_extractors.js"),
            ("web/assets/model_emitters.js", "docs/assets/model_emitters.js"),
        ]
        for source, target in pairs:
            with self.subTest(source=source):
                self.assertEqual((ROOT / source).read_text(encoding="utf-8"), (ROOT / target).read_text(encoding="utf-8"))

    def test_workbench_uses_runtime_adapter(self):
        html = (ROOT / "web" / "workbench_app.html").read_text(encoding="utf-8")
        self.assertIn('./assets/workbench_app.js', html)
        self.assertNotIn("function extractProjectFromText", html)
        self.assertIn("runtimeBadge", html)
        runtime = (ROOT / "web" / "assets" / "workbench_runtime.js").read_text(encoding="utf-8")
        self.assertIn("datasheet2spice-api-v1", runtime)
        self.assertIn("BrowserPagesBackend", runtime)
        self.assertIn("LocalPythonBackend", runtime)
        app = (ROOT / "web" / "assets" / "workbench_app.js").read_text(encoding="utf-8")
        contracts = (ROOT / "web" / "assets" / "module_contracts.js").read_text(encoding="utf-8")
        self.assertIn("./workbench_runtime.js", app)
        self.assertIn("./module_contracts.js", app)
        self.assertIn("./pdf_extractors.js", app)
        self.assertIn("./model_emitters.js", app)
        self.assertIn("WorkbenchModuleRegistry", contracts)
        self.assertIn("datasheet2spice-module-v1", contracts)

    def test_frontend_modules_expose_manifests(self):
        extractor = (ROOT / "web" / "assets" / "pdf_extractors.js").read_text(encoding="utf-8")
        emitter = (ROOT / "web" / "assets" / "model_emitters.js").read_text(encoding="utf-8")
        self.assertIn("PDF_EXTRACTOR_MODULE", extractor)
        self.assertIn("MODEL_EMITTER_MODULE", emitter)
        self.assertIn("component_profiles", extractor)
        self.assertIn("component_profiles", emitter)
        self.assertIn("DIODE_DEMO_PROJECT", extractor)
        self.assertIn("diode.power", extractor)
        self.assertIn("diode-basic", emitter)
        html = (ROOT / "web" / "workbench_app.html").read_text(encoding="utf-8")
        self.assertIn("componentProfile", html)
        self.assertIn("Diode Compact Model", html)
        self.assertIn("seriesPartSelect", html)
        self.assertIn("generateAllSeries", html)
        self.assertIn("variant_projects", extractor)

    def test_public_frontend_has_no_chinese_text(self):
        paths = [ROOT / "web" / "workbench_app.html", *sorted((ROOT / "web" / "assets").glob("*.js"))]
        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertFalse(text.startswith("\ufeff"))
                self.assertIsNone(re.search(r"[\u4e00-\u9fff]", text))


if __name__ == "__main__":
    unittest.main()
