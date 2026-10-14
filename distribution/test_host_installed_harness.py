"""Reject false installed-wheel/image claims without starting native services."""
import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


pipe = module('qualify_host_input')
lifecycle = module('qualify_host_lifecycle')


def fixture_wheel(tmp_path, change=None):
    record = 'openbexi_spell_host-0.3.1.dev1.dist-info/RECORD'
    payload = {'openbexi_spell_host/__init__.py':b"__version__ = '0.3.1.dev1'\n",
               'openbexi_spell_host/runner.py':b'# representative fixture\n',
               'openbexi_spell_host-0.3.1.dev1.dist-info/METADATA':b'Version: 0.3.1.dev1\n'}
    table = io.StringIO()
    writer = csv.writer(table, lineterminator='\n')
    for name, raw in payload.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        writer.writerow((name, 'sha256='+digest, len(raw)))
    writer.writerow((record, '', ''))
    members = dict(payload, **{record:table.getvalue().encode()})
    if change == 'tampered':
        members['openbexi_spell_host/runner.py'] = b'changed bytes\n'
    elif change == 'unrecorded':
        members['openbexi_spell_host/extra.py'] = b'unrecorded\n'
    elif change == 'traversal':
        members['../escape.py'] = b'no\n'
    elif change == 'missing':
        del members['openbexi_spell_host/runner.py']
    path = tmp_path/'host.whl'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    return path, payload


@pytest.mark.parametrize('change', ['tampered', 'unrecorded', 'traversal', 'missing'])
def test_incomplete_or_modified_wheel_is_rejected(tmp_path, change):
    wheel, _ = fixture_wheel(tmp_path, change)
    with pytest.raises(ValueError):
        pipe.wheel_payload(wheel, pipe.sha(wheel))


def test_exact_wheel_identity_and_all_record_bytes(tmp_path):
    wheel, payload = fixture_wheel(tmp_path)
    assert pipe.wheel_payload(wheel, pipe.sha(wheel)) == payload
    with pytest.raises(ValueError, match='SHA256'):
        pipe.wheel_payload(wheel, '0'*64)


@pytest.mark.parametrize('change', ['none', 'extra', 'modified', 'external-import', 'missing'])
def test_installed_payload_requires_complete_source_set_and_private_origin(tmp_path, monkeypatch, change):
    wheel, payload = fixture_wheel(tmp_path)
    prefix = tmp_path/'private'
    site = prefix/'site-packages'
    for name, raw in payload.items():
        path = site/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    origin = site/'openbexi_spell_host/__init__.py'
    if change == 'extra':
        (origin.parent/'extra.py').write_text('undeclared')
    elif change == 'modified':
        (origin.parent/'runner.py').write_text('different bytes')
    elif change == 'external-import':
        origin = tmp_path/'checkout/__init__.py'
    elif change == 'missing':
        (origin.parent/'runner.py').unlink()
    monkeypatch.setattr(pipe.sys, 'prefix', str(prefix))
    monkeypatch.setattr(pipe.sys, 'version_info', (3, 13, 15))
    monkeypatch.setattr(pipe.platform, 'python_implementation', lambda:'CPython')
    monkeypatch.setattr(pipe.metadata, 'distribution', lambda name:SimpleNamespace(
        version='0.3.1.dev1', locate_file=lambda name:site/name))
    monkeypatch.setitem(sys.modules, 'openbexi_spell_host', SimpleNamespace(
        __file__=str(origin), __version__='0.3.1.dev1'))
    if change == 'none':
        result = pipe.verify_installed_wheel(wheel, pipe.sha(wheel))
        assert result['wheel_members_verified'] == len(payload)
        assert result['package_origin'] == str(origin.resolve())
    else:
        with pytest.raises((ValueError, FileNotFoundError)):
            pipe.verify_installed_wheel(wheel, pipe.sha(wheel))


def test_pipe_binding_changes_only_exact_import_anchor(tmp_path):
    raw = (ROOT/'host_plugin/tests/test_runner_input.py').read_bytes()
    anchor = b"HOST_SOURCE = Path(__file__).resolve().parents[1] / 'src'"
    site = tmp_path/'private/site-packages'
    bound = pipe.bind_installed_tests(raw, site)
    replacement = ('HOST_SOURCE = Path('+repr(str(site.resolve()))+')').encode()
    assert bound.replace(replacement, anchor) == raw
    with pytest.raises(ValueError, match='anchor'):
        pipe.bind_installed_tests(raw.replace(anchor, b'HOST_SOURCE = None'), site)


def test_lifecycle_rejects_mutable_tag_before_any_docker_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Docker must not be called')
    monkeypatch.setattr(lifecycle.subprocess, 'check_output', forbidden)
    with pytest.raises(ValueError, match='exact local image'):
        lifecycle.exact_image('openbexi-spell-host:0.3.0')


@pytest.mark.parametrize('actual', ['sha256:'+'a'*64, 'sha256:'+'b'*64])
def test_lifecycle_checks_selected_and_live_owned_images(monkeypatch, actual):
    image = 'sha256:'+'a'*64
    monkeypatch.setattr(lifecycle.subprocess, 'check_output', lambda *args, **kwargs:actual+'\n')
    monkeypatch.setattr(lifecycle, 'containers', lambda:{'prior', 'new-owned'})
    if actual == image:
        assert lifecycle.exact_image(image) == image
        assert lifecycle.active_owned_image({'prior'}, image) == dict(container='new-owned', image=image)
    else:
        with pytest.raises(ValueError, match='differs'):
            lifecycle.exact_image(image)
        with pytest.raises(ValueError, match='different runtime'):
            lifecycle.active_owned_image({'prior'}, image)


def test_lifecycle_refuses_ambiguous_concurrent_container_ownership(monkeypatch):
    monkeypatch.setattr(lifecycle, 'containers', lambda:{'one', 'two'})
    with pytest.raises(ValueError, match='exactly one'):
        lifecycle.active_owned_image(set(), 'sha256:'+'a'*64)
