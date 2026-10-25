"""Cohort fixture contract: original native LIST wire indexes remain distinct."""

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_original_list_wire_index_and_language_value_are_not_conflated():
    before = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        spec = importlib.util.spec_from_file_location(
            "native_prompt_cohort_fixture", ROOT / "scripts/qualify_v08_native_prompts.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    historical = json.loads((ROOT / "conformance/evidence/prompt_timeout.json").read_text())

    # Independently retained original-native evidence uses index 1 for value B.
    def cases(value):
        if isinstance(value, dict):
            if "answers" in value and "result" in value:
                yield value
            for child in value.values():
                yield from cases(child)
        elif isinstance(value, list):
            for child in value:
                yield from cases(child)

    assert any(
        c["answers"] == ["1"] and c["result"].get("answer") == "B"
        for c in cases(historical)
        if isinstance(c["result"], dict)
    )
    assert module.native_list_wire_answer("answer", 0) == "0"
    assert module.native_list_wire_answer("sequential", 0) == "0"
    assert module.native_list_wire_answer("sequential", 1) == "1"
    sources = module.fixture_sources()
    assert "assert answer=='YES'" in sources["answer.py"]
    assert "assert second=='NO'" in sources["sequential.py"]
    for name, source in sources.items():
        compile(source, name, "exec")
