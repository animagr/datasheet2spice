import unittest

from datasheet2spice.plugins import load_plugins, registry
from datasheet2spice.runtime import local_runtime_capabilities, runtime_matrix
from datasheet2spice.schema import ComponentProject, DeviceProject


class ArchitectureContractTests(unittest.TestCase):
    def test_component_project_alias_keeps_existing_schema(self):
        project = ComponentProject.new("PART_A")
        self.assertIsInstance(project, DeviceProject)
        self.assertEqual(project.data["component"]["profile"], "mosfet.power")
        self.assertEqual(project.data["device"]["type"], "n_power_mosfet")

    def test_builtin_component_profile_is_registered(self):
        load_plugins(include_entrypoints=False)
        self.assertIn("mosfet.power", registry.component_profiles)
        self.assertIn("diode.power", registry.component_profiles)
        self.assertIn("mosfet.power", registry.modules)
        profile = registry.component_profiles["mosfet.power"].describe()
        self.assertIn("vdmos-static-fast", profile["supported_models"])
        self.assertEqual(profile["family"], "mosfet")
        diode_profile = registry.component_profiles["diode.power"].describe()
        self.assertIn("diode-basic", diode_profile["supported_models"])
        self.assertEqual(diode_profile["family"], "diode")

    def test_runtime_matrix_documents_pages_and_local_modes(self):
        matrix = runtime_matrix()
        names = {mode["name"] for mode in matrix["modes"]}
        self.assertIn("browser-pages", names)
        self.assertIn("local-python", names)
        self.assertEqual(local_runtime_capabilities()["active_mode"], "local-python")


if __name__ == "__main__":
    unittest.main()
