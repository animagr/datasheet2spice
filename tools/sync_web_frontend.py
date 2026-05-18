"""Sync the lightweight web frontend into the local docs tree."""

from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    (ROOT / "web" / "workbench_app.html", ROOT / "docs" / "workbench_app.html"),
    (ROOT / "web" / "assets" / "workbench_runtime.js", ROOT / "docs" / "assets" / "workbench_runtime.js"),
    (ROOT / "web" / "assets" / "workbench_app.js", ROOT / "docs" / "assets" / "workbench_app.js"),
    (ROOT / "web" / "assets" / "module_contracts.js", ROOT / "docs" / "assets" / "module_contracts.js"),
    (ROOT / "web" / "assets" / "pdf_extractors.js", ROOT / "docs" / "assets" / "pdf_extractors.js"),
    (ROOT / "web" / "assets" / "model_emitters.js", ROOT / "docs" / "assets" / "model_emitters.js"),
)


def main() -> int:
    for source, target in PAIRS:
        if not source.exists():
            raise FileNotFoundError(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"{source.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
