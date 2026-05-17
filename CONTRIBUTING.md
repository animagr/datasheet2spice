# Contributing

Thanks for helping build `datasheet2spice`.

## Development Setup

```powershell
python -m pip install -e .
$env:PYTHONPATH="$PWD\src"
python -m unittest discover -s tests -v
```

## Contribution Rules

- Keep core runtime dependencies minimal.
- Put optional AGPL/GPL/proprietary integrations behind plugins.
- Add tests for new emitters and extractors.
- Do not commit confidential datasheets, vendor encrypted models, or large simulator raw files.
- Keep generated model claims modest and traceable.

## New Emitter Checklist

- Registers through `datasheet2spice.plugins.emitter`.
- Supports at least one dialect.
- Emits deterministic text.
- Has tests.
- Documents limitations.
