"""Load the plugin's modules (checks.py, review.py, __init__.py at the
repository root) without Hermes on the path. They import each other relatively, so they are
loaded as submodules of a synthetic package rooted at the repository."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # the repository root: the installable plugin
DEV = ROOT / "dev"
PACKAGE = "prompt_refinement_under_test"

sys.path.insert(0, str(Path(__file__).parent))


def _package():
    if PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            PACKAGE, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = module
        spec.loader.exec_module(module)
    return sys.modules[PACKAGE]


def load_module(name: str):
    if name == "__init__":
        return _package()
    _package()
    return importlib.import_module(f"{PACKAGE}.{name}")
