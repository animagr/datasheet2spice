import unittest

import datasheet2spice.plugins as plugins


class _FakeEntryPoint:
    name = "fake-plugin"

    def load(self):
        def register(registry):
            registry.extractors["fake-extractor"] = object()

        return register


class _FakeEntryPoints:
    def select(self, group):
        return [_FakeEntryPoint()] if group == "datasheet2spice.plugins" else []


class _FailingEntryPoint:
    name = "bad-plugin"

    def load(self):
        raise RuntimeError("boom")


class _FailingEntryPoints:
    def select(self, group):
        return [_FailingEntryPoint()] if group == "datasheet2spice.plugins" else []


class PluginTests(unittest.TestCase):
    def test_entrypoint_plugins_can_register(self):
        original = plugins.entry_points
        try:
            plugins.entry_points = lambda: _FakeEntryPoints()
            loaded = plugins.load_entrypoint_plugins()
        finally:
            plugins.entry_points = original
            plugins.registry.extractors.pop("fake-extractor", None)
        self.assertEqual(loaded, ["fake-plugin"])

    def test_entrypoint_plugin_failures_are_recorded(self):
        original = plugins.entry_points
        try:
            plugins.entry_points = lambda: _FailingEntryPoints()
            loaded = plugins.load_entrypoint_plugins()
        finally:
            plugins.entry_points = original
        self.assertEqual(loaded, [])
        self.assertEqual(len(plugins.plugin_load_errors), 1)
        self.assertIn("bad-plugin", plugins.plugin_load_errors[0])


if __name__ == "__main__":
    unittest.main()
