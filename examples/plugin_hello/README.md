# Hello Plugin Example

This is a tiny external-plugin sketch. It is not installed by default, but it
shows the packaging shape third-party emitters, extractors, and validators can
use.

```powershell
cd examples/plugin_hello
python -m pip install -e .
datasheet2spice plugins
datasheet2spice emit ..\demo_sic_mosfet\device.json --model hello-emitter --out ..\..\build\hello
```

The `hello-emitter` output is only a smoke-test file, not a useful SPICE model.
