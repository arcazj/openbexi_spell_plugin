"""Bind v0.4 / neutral IDE v0.3 acceptance to checked source, images and wheels."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
IDE = ROOT.parent/'openbexi_ide'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(path):
    return dict(path=str(path.resolve()),sha256=sha(path))


def docker(*args):
    return subprocess.check_output(['docker',*args],timeout=30)


def counts(path):
    suites = ET.parse(path).findall('.//testsuite')
    result = {k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    assert result['tests'] and not any(result[k] for k in ('failures','errors','skipped')),result
    return dict(**result,**evidence(path))


def wheel(path,source):
    with ZipFile(path) as archive:
        for file in source.rglob('*.py'):
            assert archive.read(file.relative_to(source).as_posix()).replace(b'\r\n',b'\n') == file.read_bytes().replace(b'\r\n',b'\n'),file
    return evidence(path)


def main():
    q = ROOT/'.qualification/v0.4'
    iq = IDE/'.qualification/v0.4'
    artifacts = {
        'driver':wheel(q/'release-wheels/openbexi_spell_dss-0.4.0-py3-none-any.whl',ROOT/'driver_plugin/src'),
        'provider':wheel(q/'release-wheels-final/openbexi_spell_shared-0.4.0-py3-none-any.whl',ROOT/'shared_plugin/src'),
        'bounded_dss_service':wheel(q/'release-wheels-final/openbexi_spell_plugin-0.1.0-py3-none-any.whl',ROOT/'src'),
        'core':wheel(iq/'release-wheels-final/openbexi_ide-0.3.0-py3-none-any.whl',IDE/'src'),
        'host':evidence(ROOT/'.qualification/v0.3/host-wheels/openbexi_spell_host-0.3.0-py3-none-any.whl')}
    installed = json.loads((q/'installed-acceptance-01/result.json').read_text())
    core_installed = json.loads((iq/'core-installed-acceptance-01/result.json').read_text())
    assert installed['passed'] and core_installed['passed']
    assert core_installed['wheel_sha256'] == artifacts['core']['sha256']
    tests = {
        'core':counts(iq/'core-final.xml'),
        'release_validation_supplement':counts(iq/'release-validation-final.xml'),
        'plugin':counts(q/'plugin-final.xml'),
        'legacy_native':counts(iq/'native-legacy-final.xml'),
        'installed_driver_native_kafka':counts(q/'installed-acceptance-01/tests.xml')}
    assert tests['core']['tests'] >= 104 and tests['plugin']['tests'] >= 204
    assert tests['legacy_native']['tests'] == 11 and tests['installed_driver_native_kafka']['tests'] == 48
    base = json.loads(docker('image','inspect','openbexi-spell-host:0.3.0'))[0]
    assert base['Id'] == 'sha256:69d29bcd6ec4cd27f822224b723546be15e2de3b5b9d3f38d442b91249c1833d'
    image = json.loads(docker('image','inspect','openbexi-spell-dss:0.4.0'))[0]
    assert image['RootFS']['Layers'][:len(base['RootFS']['Layers'])] == base['RootFS']['Layers']
    code = """import hashlib,importlib.metadata as m,json,sys
from pathlib import Path
import openbexi_spell_dss
print(json.dumps(dict(python=sys.version,driver=m.version('openbexi-spell-dss'),
 packages=sorted([dict(name=d.metadata['Name'],version=d.version) for d in m.distributions()],key=lambda r:r['name']),
 wheel_sha256=hashlib.sha256(next(Path('/opt/driver-wheels').glob('*.whl')).read_bytes()).hexdigest(),
 host={p.name:hashlib.sha256(p.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for p in Path('/opt/host').glob('*.py')})))"""
    identity = uuid.uuid4().hex
    name = 'openbexi-v04-provenance-'+identity
    try:
        runtime = json.loads(docker('run','--rm','--name',name,'--label','org.openbexi.qualification='+identity,
            '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--entrypoint=python',image['Id'],'-I','-c',code))
    finally:
        rows = docker('ps','-a','--filter','name=^/'+name+'$','--format','{{.ID}}').strip()
        if rows:
            remaining = json.loads(docker('inspect',name))[0]
            assert remaining['Config']['Labels']['org.openbexi.qualification'] == identity
            docker('rm','--force',remaining['Id'])
    assert runtime['driver'] == '0.4.0' and runtime['wheel_sha256'] == artifacts['driver']['sha256']
    for file in (ROOT/'host_runtime/python').glob('*.py'):
        assert runtime['host'][file.name] == hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    contracts = ROOT/'driver_plugin/src/openbexi_spell_dss/contracts'
    provenance = json.loads((contracts/'provenance.json').read_text())
    assert sha(ROOT/'docs/reference/SPELL2.6.10-src.zip') == provenance['archive_sha256']
    assert sha(contracts/'SPELLDriver.proto') == provenance['schema_sha256']
    sources = {}
    for prefix,root,patterns in (
        ('plugin',ROOT,['src/**/*.py','src/dss/data/*.json','driver_plugin/src/**/*.py','driver_plugin/src/**/*.proto',
            'driver_plugin/src/**/provenance.json','driver_plugin/pyproject.toml','driver_plugin/Dockerfile*',
            'host_runtime/python/*.py','shared_plugin/src/**/*.py','shared_plugin/pyproject.toml',
            'scripts/*driver*.py','tests/test_original_driver.py','tests/kafka_driver_acceptance.py','docs/DRIVER_RUNTIME.md']),
        ('ide',IDE,['src/**/*.py','tests/*.py','pyproject.toml','docs/PLUGIN_EXECUTION_SERVICE.md'])):
        for pattern in patterns:
            for file in root.glob(pattern):
                if file.is_file():
                    sources[prefix+'/'+file.relative_to(root).as_posix()] = hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    result = dict(schema='openbexi.original-driver-qualification/1',release='0.4.0',ide_release='0.3.0',
        release_accepted=True,qualified_utc=datetime.now(timezone.utc).isoformat(),
        scope='Original native driver and operating modes for the declared GENERIC simulator profile',
        platform=platform.platform(),python=platform.python_version(),
        base_commits={name:subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
                      for name,root in [('plugin',ROOT),('ide',IDE)]},
        image=dict(id=image['Id'],base=base['Id'],layers=image['RootFS']['Layers'],runtime=runtime),
        contracts=provenance,artifacts=artifacts,tests=tests,installed=installed,
        installed_evidence=evidence(q/'installed-acceptance-01/result.json'),
        neutral_installed_evidence=evidence(iq/'core-installed-acceptance-01/result.json'),
        neutral_installed_checks=core_installed['checks'],
        prior_native_acceptance=evidence(ROOT/'docs/HOST_QUALIFICATION.json'),
        source_sha256_lf=sources,
        limits=['GENERIC simulator only; no operational procedure approval',
            'Windows x64 service and Linux amd64 Docker; single durable authority',
            'Trusted installed provider, service OS account and Docker administrator',
            'Critical/scheduled TC, vendor Cortex, unused EV streams and full mission semantics remain v0.5',
            '763-row inventory classifications are not promoted by this milestone',
            'Independent reproducibility, transitive supplier audits and supported upgrades remain later gates',
            'Private loopback driver RPC; local trusted DSS/Kafka qualification, not remote broker security',
            'Shared native debugger inspection remains separate; old host image and JetBrains ZIP unchanged'])
    target = ROOT/'docs/DRIVER_QUALIFICATION.json'
    target.write_text(json.dumps(result,indent=2)+'\n',newline='\n')
    neutral = dict(schema='openbexi.plugin-execution-qualification/1',release='0.3.0',release_accepted=True,
        qualified_utc=result['qualified_utc'],scope='Single-authority durable service with approved Python/plugin Execution and fenced provider effects',
        core_artifact=artifacts['core'],tests=tests,neutral_installed_evidence=result['neutral_installed_evidence'],
        neutral_installed_checks=core_installed['checks'],driver_acceptance=evidence(target),limits=result['limits'])
    (IDE/'docs/PLUGIN_EXECUTION_QUALIFICATION.json').write_text(json.dumps(neutral,indent=2)+'\n',newline='\n')
    print(json.dumps(dict(accepted=True,image=image['Id'],tests={k:v['tests'] for k,v in tests.items()})))


if __name__ == '__main__':
    main()
