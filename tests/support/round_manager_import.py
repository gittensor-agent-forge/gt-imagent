from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_round_manager() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "round_manager.py"
    spec = importlib.util.spec_from_file_location("round_manager", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load round_manager.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
