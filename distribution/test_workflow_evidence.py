"""Reject false source/image/artifact qualification without running Docker."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import workflow_evidence as proof
import record_workflows as recorder


def make_wheel(tmp_path, mutation=None):
    rows = {'sample/__init__.py':b'x=1\n','sample/item.py':b'value=42\n',
            'sample-1.dist-info/METADATA':b'Name: sample\nVersion: 1\n'}
    record = 'sample-1.dist-info/RECORD'
    table = io.StringIO()
    writer = csv.writer(table,lineterminator='\n')
    for name,raw in rows.items():
        encoded=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256='+encoded,len(raw)))
    writer.writerow((record,'',''))
    entries = dict(rows,**{record:table.getvalue().encode()})
    if mutation=='changed':
        entries['sample/item.py']=b'changed\n'
    elif mutation=='unrecorded':
        entries['sample/extra.py']=b'extra\n'
    elif mutation=='missing':
        entries.pop('sample/item.py')
    path=tmp_path/'sample.whl'
    with zipfile.ZipFile(path,'w') as archive:
        for name,raw in entries.items():
            archive.writestr(name,raw)
    return path,rows


@pytest.mark.parametrize('mutation',['changed','unrecorded','missing'])
def test_record_rejects_tampered_or_incomplete_payload(tmp_path,mutation):
    path,_=make_wheel(tmp_path,mutation)
    with pytest.raises(ValueError,match='RECORD'):
        proof.wheel(path)


@pytest.mark.parametrize('mutation',['none','extra-source','extra-pyd','extra-so','extra-pyc','changed-source','metadata','external-install'])
def test_installed_artifacts_bind_every_member_and_complete_source_set(tmp_path,monkeypatch,mutation):
    path,rows=make_wheel(tmp_path)
    prefix=tmp_path/'environment'
    site=(prefix if mutation!='external-install' else tmp_path/'external')/'site-packages'
    for name,raw in rows.items():
        target=site/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
    if mutation=='extra-source':
        (site/'sample/extra.py').write_bytes(b'undeclared\n')
    elif mutation.startswith('extra-'):
        (site/('sample/extra.'+mutation.split('-')[1])).write_bytes(b'undeclared\n')
    elif mutation=='changed-source':
        (site/'sample/item.py').write_bytes(b'wrong\n')
    elif mutation=='metadata':
        (site/'sample-1.dist-info/METADATA').write_bytes(b'Name: sample\nVersion: wrong\n')
    monkeypatch.setattr(proof.sys,'prefix',str(prefix))
    monkeypatch.setattr(proof.metadata,'distribution',lambda name:SimpleNamespace(version='1',locate_file=lambda name:site/name))
    bindings={'sample':dict(path=str(path),sha256=proof.sha(path))}
    if mutation=='none':
        result=proof.installed_wheels(bindings,tmp_path)
        assert result['sample']['installed_members_verified']==3
    else:
        with pytest.raises(ValueError,match='Installed'):
            proof.installed_wheels(bindings,tmp_path)


@pytest.mark.parametrize('mutation',['none','duplicate-path','wrong-spec','changed-bytes','external-prefix'])
def test_executed_import_is_exact_selected_distribution_member(tmp_path,monkeypatch,mutation):
    path,rows=make_wheel(tmp_path)
    prefix=tmp_path/'environment'
    site=prefix/'site-packages'
    for name,raw in rows.items():
        target=site/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
    expected=site/'sample/__init__.py'
    duplicate=prefix/'stale/sample/__init__.py'
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(expected.read_bytes())
    origin=duplicate if mutation=='duplicate-path' else expected
    spec=duplicate if mutation=='wrong-spec' else origin
    if mutation=='changed-bytes':expected.write_bytes(b'stale\n')
    monkeypatch.setattr(proof.sys,'prefix',str(tmp_path/'other' if mutation=='external-prefix' else prefix))
    monkeypatch.setattr(proof.metadata,'distribution',lambda name:SimpleNamespace(version='1',locate_file=lambda name:site/name))
    monkeypatch.setattr(proof.importlib,'import_module',lambda name:SimpleNamespace(__file__=str(origin),__spec__=SimpleNamespace(origin=str(spec))))
    bindings={'sample':dict(path=str(path),sha256=proof.sha(path))}
    if mutation=='none':
        assert proof.imported_modules(bindings,{'sample':'sample'},tmp_path)['sample']['member']=='sample/__init__.py'
    else:
        with pytest.raises(ValueError,match='Executed import'):
            proof.imported_modules(bindings,{'sample':'sample'},tmp_path)


@pytest.mark.parametrize('mutation',['none','wrong-plugin','wrong-product','wrong-sdk','changed-sdk','stale-verdict','changed-command','wrong-version','failed'])
def test_verifier_binds_artifact_product_sdk_tool_and_verdict(tmp_path,mutation):
    inputs=tmp_path/'inputs'
    inputs.mkdir()
    java=inputs/'java.exe'
    java.write_bytes(b'pinned java')
    plugin=inputs/'plugin.zip'
    plugin.write_bytes(b'pinned plugin')
    verifier=inputs/'verifier.jar'
    with zipfile.ZipFile(verifier,'w') as archive:
        archive.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nVerifier-Version: 1.410\n')
    sdk=inputs/'sdk'
    sdk.mkdir()
    product=dict(name='PyCharm',version='2026.1',buildNumber='261.1',productCode='PY')
    metadata=sdk/'product-info.json'
    metadata.write_text(json.dumps(product))
    output=tmp_path/'result'
    verdict=output/'reports/plugin/sdk/verification-verdict.txt'
    verdict.parent.mkdir(parents=True)
    verdict.write_text('Compatible.\n')
    paths=dict(java=java,plugin=plugin,verifier=verifier)
    raw=dict(passed=True,harness_sha256=proof.sha(recorder.ROOT/'distribution/qualify_plugin_verifier.py'),
        exit_code=0,plugin_sha256=proof.sha(plugin),sdk=product,sdk_path=str(sdk),
        sdk_metadata_sha256=proof.sha(metadata),inputs={n:dict(path=str(p),sha256=proof.sha(p)) for n,p in paths.items()},
        command=[str(java),'-jar',str(verifier),'check-plugin',str(plugin),str(sdk),'-verification-reports-dir',str(output/'reports')],
        verifier_version='1.410',verdict=dict(path=verdict.relative_to(output).as_posix(),sha256=proof.sha(verdict)),
        evidence_files={verdict.relative_to(output).as_posix():proof.sha(verdict)})
    workflow=dict(sdk=dict(product),sdk_metadata_sha256=proof.sha(metadata))
    if mutation=='wrong-plugin':raw['plugin_sha256']='0'*64
    elif mutation=='wrong-product':raw['sdk']=dict(product,productCode='IU')
    elif mutation=='wrong-sdk':workflow['sdk']['buildNumber']='262.2'
    elif mutation=='changed-sdk':metadata.write_text('{}')
    elif mutation=='stale-verdict':verdict.write_text('Compatible. Different run.\n')
    elif mutation=='changed-command':raw['command'][4]=str(inputs/'other.zip')
    elif mutation=='wrong-version':raw['verifier_version']='1.409'
    elif mutation=='failed':raw['exit_code']=1
    result=output/'result.json'
    result.write_text(json.dumps(raw))
    if mutation=='none':
        assert recorder.verifier_report(result,workflow,'PY',proof.sha(plugin))['passed']
    else:
        with pytest.raises(ValueError):
            recorder.verifier_report(result,workflow,'PY',proof.sha(plugin))


def test_wheel_source_comparison_rejects_extra_and_changed_sources(tmp_path):
    path,rows=make_wheel(tmp_path)
    source=tmp_path/'src'
    for name,raw in rows.items():
        if name.endswith('.py'):
            target=source/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
    assert proof.wheel_source(path,source)['name']=='sample'
    (source/'sample/item.py').write_text('modified')
    with pytest.raises(ValueError,match='source set/bytes'):
        proof.wheel_source(path,source)


def test_input_references_reject_hash_drift_and_unbound_paths(tmp_path):
    path=tmp_path/'input.json'
    path.write_text('{}')
    binding=dict(path=path.name,sha256=proof.sha(path))
    assert proof.bound_file(binding,tmp_path)==path
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='SHA256'):
        proof.bound_file(binding,tmp_path)
    with pytest.raises(ValueError,match='exact path'):
        proof.bound_file(path.name,tmp_path)


@pytest.mark.parametrize('mutation',['wrong-image','tag','failed'])
def test_workflow_cannot_mix_image_or_failed_result(tmp_path,mutation):
    expected='sha256:'+'a'*64
    actual='sha256:'+'b'*64 if mutation=='wrong-image' else expected
    path=tmp_path/'result.json'
    path.write_text(json.dumps(dict(passed=mutation!='failed',image=actual)))
    with pytest.raises(ValueError):
        if mutation=='tag':
            proof.exact_image('openbexi-spell-host:0.3.0')
        else:
            recorder.checked_report(path,expected)


@pytest.mark.parametrize('mutation',['empty','failure','skip'])
def test_junit_does_not_allow_empty_failed_or_skipped_qualification(tmp_path,mutation):
    path=tmp_path/'tests.xml'
    path.write_text('<testsuites><testsuite tests="'+('0' if mutation=='empty' else '1')+
        '" failures="'+('1' if mutation=='failure' else '0')+'" errors="0" skipped="'+
        ('1' if mutation=='skip' else '0')+'"/></testsuites>')
    with pytest.raises(ValueError,match='JUnit'):
        recorder.counts(path)


@pytest.mark.parametrize('mutation',['none','wrong-platform','stale-harness','different-wheel','missing-case','changed-journal'])
def test_pipe_record_requires_platform_artifact_harness_and_retained_evidence(tmp_path,mutation):
    wheel={'sha256':'f'*64,'members':{'openbexi_spell_host/runner.py':'e'*64}}
    junit=tmp_path/'tests.xml'
    junit.write_text('<testsuites><testsuite tests="16" failures="0" errors="0" skipped="0">'+
        ''.join('<testcase name="case'+str(n)+'"/>' for n in range(16))+'</testsuite></testsuites>')
    original=(recorder.ROOT/'host_plugin/tests/test_runner_input.py').read_bytes()
    (tmp_path/'original_test_runner_input.py').write_bytes(original)
    site='/private/lib/python3.13/site-packages'
    adapted=original.decode().replace("HOST_SOURCE = Path(__file__).resolve().parents[1] / 'src'",
        'HOST_SOURCE = Path('+repr(site)+')').encode()
    (tmp_path/'test_runner_input.py').write_bytes(adapted)
    raw=dict(passed=True,harness_sha256=proof.sha(recorder.ROOT/'scripts/qualify_host_input.py'),
        original_tests_sha256=proof.sha(recorder.ROOT/'host_plugin/tests/test_runner_input.py'),
        expected_platform='Linux',installed=dict(platform='Linux',wheel_sha256=wheel['sha256'],installed_members=wheel['members'],
            package_origin=site+'/openbexi_spell_host/__init__.py'),adapted_tests_sha256=hashlib.sha256(adapted).hexdigest(),
        tests=dict(tests=16,failures=0,errors=0,skipped=0),exit_code=0,
        evidence_files={p.name:proof.sha(p) for p in tmp_path.iterdir() if p.is_file()})
    if mutation=='wrong-platform':raw['installed']['platform']='Windows'
    elif mutation=='stale-harness':raw['harness_sha256']='0'*64
    elif mutation=='different-wheel':raw['installed']['wheel_sha256']='0'*64
    elif mutation=='missing-case':raw['tests']['tests']=15
    elif mutation=='changed-journal':junit.write_text('changed')
    path=tmp_path/'result.json'
    path.write_text(json.dumps(raw))
    if mutation=='none':
        assert recorder.pipe_report(path,'Linux',wheel)['passed']
    else:
        with pytest.raises(ValueError):
            recorder.pipe_report(path,'Linux',wheel)
