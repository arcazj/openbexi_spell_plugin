"""Development installed-wheel supply chain scanner: no promotion to release gate."""

import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "dev43_scoped_supply", ROOT / "scripts/qualify_v08_supply_chain.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: "a" * 40)
    wheel = tmp_path / "openbexi_spell_server-0.8.0.dev43-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr("openbexi_spell_server/__init__.py", "__version__ = '0.8.0.dev43'\n")
        z.writestr("openbexi_spell_server-0.8.0.dev43.dist-info/licenses/LICENSE", "Apache-2.0")
    sbom = tmp_path / "sbom.json"
    sbom.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "components": [{"name": "openbexi-spell-server", "version": "0.8.0.dev43"}],
            }
        )
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "openbexi-spell-server", "version": "0.8.0.dev43", "vulns": []}
                ]
            }
        )
    )
    return wheel, sbom, audit


def test_scoped_supply_chain_assessment_never_authorizes_release(sample, tmp_path):
    result = module.assess(tmp_path, *sample)
    assert result["passed"] is True
    assert result["full_v08_qualified"] is False
    assert result["independent_security_qualified"] is False
    assert result["wheel_file_count"] == 2
    assert result["sbom_components"] == 1


def test_scoped_vulnerability_is_exposed_not_silently_ignored(sample, tmp_path):
    wheel, sbom, audit = sample
    audit.write_text(
        json.dumps(
            {
                "dependencies": [
                    {
                        "name": "openbexi-spell-server",
                        "version": "0.8.0.dev43",
                        "vulns": [{"id": "TEST-CVE-0001"}],
                    }
                ]
            }
        )
    )
    result = module.assess(tmp_path, wheel, sbom, audit)
    assert not result["passed"]
    assert result["known_vulnerable_dependencies"] == [
        {"name": "openbexi-spell-server", "version": "0.8.0.dev43"}
    ]
    assert result["full_v08_qualified"] is False


@pytest.mark.parametrize(
    "changed",
    [
        {
            "bomFormat": "INVALID",
            "components": [{"name": "openbexi-spell-server", "version": "0.8.0.dev43"}],
        },
        {
            "bomFormat": "CycloneDX",
            "components": [{"name": "openbexi-spell-server", "version": "0.8.0.dev42"}],
        },
        {"bomFormat": "CycloneDX", "components": []},
    ],
)
def test_refuse_incomplete_or_stale_development_sbom(sample, tmp_path, changed):
    wheel, sbom, audit = sample
    sbom.write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        module.assess(tmp_path, wheel, sbom, audit)


def test_cannot_include_private_pem_in_distribution(sample, tmp_path):
    wheel, sbom, audit = sample
    with zipfile.ZipFile(wheel, "a") as z:
        z.writestr(
            "openbexi_spell_server/private.pem",
            "-----BEGIN PRIVATE KEY-----\nBAD\n-----END PRIVATE KEY-----\n",
        )
    with pytest.raises(ValueError, match="private PEM"):
        module.assess(tmp_path, wheel, sbom, audit)


def test_missing_license_or_vulnerability_inventory_cannot_pass(sample, tmp_path):
    wheel, sbom, audit = sample
    audit.write_text(json.dumps({"dependencies": []}))
    with pytest.raises(ValueError, match="inventory"):
        module.assess(tmp_path, wheel, sbom, audit)
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr("openbexi_spell_server/__init__.py", "from pathlib import Path")
    with pytest.raises(ValueError, match="license"):
        module.assess(tmp_path, wheel, sbom, audit)
