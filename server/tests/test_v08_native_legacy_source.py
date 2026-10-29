import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("host_runtime/build_admission_context.py", "legacy_source_builder")
generator = module("scripts/generate_v08_legacy_syntax.py", "legacy_header_generator")
UNITS = ("lib/SPELL_EXC/src/SPELLastAnalyzer.C", "lib/SPELL_UTIL/src/SPELLpythonHelper.C")


def old_helper():
    # Exact Git blob5ee156a884cff8d6990e88add8128594676fbada from546ca4a,
    # retained as an explicit historical fixture, not fresh runtime evidence.
    raw = (ROOT / "server/tests/data/native_frozen_legacy_syntax.py").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "f287f9062a7775a8c4bb929759811f5c9a168eafa4c507aeb5b08f05a37f2ca0"
    )
    return raw


def fixture(tmp_path):
    source, recipe = tmp_path / "source", tmp_path / "recipe"
    recipe.mkdir()
    (recipe / "legacy_compare_syntax.py").write_bytes(old_helper())
    (source / "include/SPELL_UTIL").mkdir(parents=True)
    literal = json.dumps(old_helper().decode(), ensure_ascii=True)
    for name in UNITS:
        path = source / name
        path.parent.mkdir(parents=True)
        path.write_text(
            "// unchanged surrounding native code\nPyRun_String("
            + literal
            + ", Py_file_input, env, env);\n"
        )
    return source, recipe, ROOT / "host_runtime/native/legacy_syntax.H"


def test_generated_header_exactly_contains_current_tracked_helper():
    source = (ROOT / "source_port/legacy_compare_syntax.py").read_bytes()
    assert (
        hashlib.sha256(source).hexdigest()
        == "7817b95a89d1e960c4183b4bc8c411088f642a084c0bc8777e2790409f2ae228"
    )
    assert (
        generator.generated(source) == (ROOT / "host_runtime/native/legacy_syntax.H").read_bytes()
    )


def test_old_actual_helper_fails_adjacent_token_and_current_helper_recovers():
    code = b"assert (1 <> 2) is True\nassert (2 <> 2) is False\n"
    before, after = {}, {}
    exec(compile(old_helper(), "frozen-legacy-helper", "exec"), before)
    exec(
        compile(
            (ROOT / "source_port/legacy_compare_syntax.py").read_bytes(),
            "tracked-legacy-helper",
            "exec",
        ),
        after,
    )
    assert before["normalize"](code) == code
    with pytest.raises(SyntaxError):
        compile(before["normalize"](code), "unchanged-original-case", "exec")
    exec(compile(after["normalize"](code), "unchanged-original-case", "exec"), {})


def test_refresh_is_narrow_and_frozen_provenance_unchanged(tmp_path):
    source, recipe, header = fixture(tmp_path)
    frozen = (recipe / "legacy_compare_syntax.py").read_bytes()
    originals = {name: (source / name).read_text() for name in UNITS}
    result = builder.refresh_native_legacy_syntax(source, recipe, header)
    assert result["original_provenance_unchanged"] is True
    assert result["native_runtime_qualified"] is False
    assert (recipe / "legacy_compare_syntax.py").read_bytes() == frozen
    for name in UNITS:
        expected = '#include "SPELL_UTIL/v08_legacy_syntax.H"\n' + originals[name].replace(
            "PyRun_String(" + json.dumps(frozen.decode(), ensure_ascii=True) + ", Py_file_input",
            "PyRun_String(v08LegacySyntax, Py_file_input",
        )
        assert (source / name).read_text() == expected
    assert (source / "include/SPELL_UTIL/v08_legacy_syntax.H").read_bytes() == header.read_bytes()


@pytest.mark.parametrize(
    "mutation", ["old-helper", "header", "first-unit", "second-unit", "existing-destination"]
)
def test_drift_or_reapplication_refused_before_any_unit_write(tmp_path, mutation):
    source, recipe, header = fixture(tmp_path)
    if mutation == "old-helper":
        (recipe / "legacy_compare_syntax.py").write_text("changed")
    elif mutation == "header":
        header = tmp_path / "bad.H"
        header.write_text("changed")
    elif mutation.endswith("unit"):
        (source / UNITS[0 if mutation == "first-unit" else 1]).write_text("changed")
    else:
        (source / "include/SPELL_UTIL/v08_legacy_syntax.H").write_text("already installed")
    before = {name: (source / name).read_bytes() for name in UNITS}
    with pytest.raises(ValueError):
        builder.refresh_native_legacy_syntax(source, recipe, header)
    assert {name: (source / name).read_bytes() for name in UNITS} == before


def test_header_cannot_capture_raw_string_terminator_or_nul():
    for value in (b')v08_legacy"', b"\x00"):
        with pytest.raises(ValueError):
            generator.generated(value)


def test_cpp_header_exports_exact_authoritative_bytes(tmp_path):
    code = tmp_path / "header.cpp"
    code.write_text(
        '#include "'
        + str(ROOT / "host_runtime/native/legacy_syntax.H")
        + '"\n#include <cstdio>\nint main(){return fwrite(v08LegacySyntax,1,sizeof(v08LegacySyntax)-1,stdout)==sizeof(v08LegacySyntax)-1?0:1;}\n'
    )
    program = tmp_path / "header"
    subprocess.run(
        ["c++", "-std=c++17", str(code), "-o", str(program)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert (
        subprocess.check_output([program], timeout=10)
        == (ROOT / "source_port/legacy_compare_syntax.py").read_bytes()
    )
