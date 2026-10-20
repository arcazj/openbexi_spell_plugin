"""Accept v0.6 only after exact final artifacts and every release gate agree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
from aggregate_support import complete_sequence
from check import validate
from build_images import inspect_wheel
from run_language_regressions import validate_report


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def ref(path):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def read(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    args=parser.parse_args()
    bindings=read(args.inputs)
    paths={}
    for name,row in bindings.items():
        path=Path(row['path']).resolve(strict=True)
        assert sha(path)==row['sha256'],name
        paths[name]=path
    required={
        'native_pair','driver_pair','images','host_pair','shared_pair','sdk_pair',
        'jetbrains_a','jetbrains_b','verifier_intellij','verifier_pycharm',
        'python_upgrade_windows','python_upgrade_linux','native_upgrade',
        'openbexi','openbexi_upgrade','intellij','pycharm','installed_driver',
        'host_adapter','host_lifecycle','sequence','refresh','promotions',
        'controls','repository_junit','portable','runtime_archive','build_environment_archive',
        'offline_inputs_archive','toolchain_capture','toolchain_reconstruction',
        'native_wheel','driver_wheel','host_wheel','shared_wheel','sdk_wheel','jetbrains_zip',
    }
    assert set(paths)==required, sorted(required^set(paths))
    reports={name:read(path) for name,path in paths.items() if path.suffix=='.json'}
    for name,report in reports.items():
        if name not in {'jetbrains_a','jetbrains_b','host_adapter'}:
            assert report['passed'] is True,name
    images=reports['images']
    image,host=images['driver_plugin']['image'],images['host_runtime']['image']
    pair=reports['native_pair']
    assert all(pair['checks'].values()) and pair['same_build_repackaging'] is False
    assert pair['native_build_network']=='none' and pair['build_cache_enabled'] is False
    native=inspect_wheel(paths['native_wheel'],require_composition=True)
    driver=inspect_wheel(paths['driver_wheel'],require_driver_composition=True)
    assert native==images['native_wheel'] and driver==images['driver_wheel']
    assert all(p['sha256']==native['sha256'] for p in pair['packages'])
    assert len(pair['packages'])==2
    assert len(reports['driver_pair']['wheels'])==2
    assert all(p['sha256']==driver['sha256'] for p in reports['driver_pair']['wheels'])
    for name,artifact in [('host_pair','host_wheel'),('shared_pair','shared_wheel'),('sdk_pair','sdk_wheel')]:
        builds=reports[name]['builds']
        assert len(builds)==2 and all(row['sha256']==sha(paths[artifact]) for row in builds),name
        assert all(sha(ROOT/path)==digest for path,digest in reports[name]['inputs'].items())
    plugin=sha(paths['jetbrains_zip'])
    assert reports['jetbrains_a']['sha256']==reports['jetbrains_b']['sha256']==plugin
    for name in ('verifier_intellij','verifier_pycharm','intellij','pycharm'):
        assert reports[name]['plugin_sha256']==plugin,name
    for name in ('intellij','pycharm'):
        report=reports[name]
        assert report['image']==image
        assert report['installed_host']['wheel_sha256']==sha(paths['host_wheel'])
        for phase in ('previous','upgraded','removed'):
            raw=read(paths[name].parent/report[phase]['result'])
            assert raw['passed'] and raw['runtime_images']==[image]
            assert sha(paths[name].parent/report[phase]['result'])==report[phase]['sha256']
        assert report['upgraded']['preferences_preserved']==report['previous']['configured_preferences']
        preservation=report['upgraded']['project_preservation']
        assert preservation['before']==preservation['after']
    for name in ('openbexi','openbexi_upgrade','installed_driver','controls'):
        assert reports[name]['image']==image,name
    for name,count in [('child-arguments',10),('child-modes',9),('child-modes-repeat',9),
                       ('duplicate-answers',24),('abort-prompts',12)]:
        row=reports['controls']['stages'][name]
        assert row['exit_code']==0
        assert validate_report(Path(row['raw']['path']),image,count)==row['raw']
    assert reports['openbexi']['host_wheel_sha256']==sha(paths['host_wheel'])
    assert reports['openbexi_upgrade']['wheel_sha256']==sha(paths['host_wheel'])
    for name in ('host_adapter','host_lifecycle'):
        assert reports[name]['image']==host,name
    assert reports['host_adapter']['tests']==14
    assert not reports['host_adapter']['failures'] and not reports['host_adapter']['errors']
    assert all(sha(ROOT/name)==digest for name,digest in reports['host_adapter']['inputs'].items())
    installed=reports['installed_driver']['installed_wheels']
    for distribution,artifact in [('openbexi-spell-dss','driver_wheel'),('openbexi-spell-host','host_wheel'),
                                 ('openbexi-spell-shared','shared_wheel'),('openbexi-spell-plugin','sdk_wheel')]:
        assert installed[distribution]['sha256']==sha(paths[artifact])
    for row in reports['native_upgrade']['inputs']['target']:
        artifact={'openbexi-spell-source':'native_wheel','openbexi-spell-dss':'driver_wheel'}[row['name']]
        assert row['version']=='0.6.0' and row['sha256']==sha(paths[artifact])
    for row in reports['python_upgrade_windows']['inputs']['target']:
        artifact={'openbexi-spell-host':'host_wheel','openbexi-spell-shared':'shared_wheel'}[row['name']]
        assert row['version']=='0.6.0' and row['sha256']==sha(paths[artifact])
    linux=reports['python_upgrade_linux']
    assert sha(linux['result'])==linux['result_sha256']
    for label,artifact in [('host','host_wheel'),('shared','shared_wheel')]:
        assert linux['inputs'][label]['sha256']==sha(paths[artifact])
    sequence,_,_,_=complete_sequence(paths['sequence'],('context-startup','prompt-complete'))
    assert sequence['image']==image and len(sequence['suites'])==61
    assert sum(row['raw']['checks'] for row in sequence['suites'])==2157
    gate=validate(read(ROOT/'conformance/inventory.json'),read(ROOT/'conformance/coverage.json'),ROOT)
    assert gate['accepted'] and gate['counts']=={'QUALIFIED':763} and gate['total']==763
    assert reports['promotions']['coverage_sha256']==sha(ROOT/'conformance/coverage.json')
    assert reports['promotions']['runtime_image']==image
    totals={key:sum(int(s.get(key,'0')) for s in ET.parse(paths['repository_junit']).iter('testsuite'))
            for key in ('tests','failures','errors','skipped')}
    assert totals['tests']>=1421 and totals['failures']==totals['errors']==totals['skipped']==0
    portable=reports['portable']
    assert not portable['issues']
    assert set(reports['runtime_archive']['images'])=={image,host}
    assert reports['runtime_archive']['descriptor_graph_verified']
    assert reports['build_environment_archive']['descriptor_graph_verified']
    artifacts={name:ref(paths[name]) for name in
               ('native_wheel','driver_wheel','host_wheel','shared_wheel','sdk_wheel','jetbrains_zip')}
    for name in ('portable','runtime_archive','build_environment_archive','offline_inputs_archive'):
        row=reports[name]['archive']
        assert sha(row['path'])==row['sha256'] and Path(row['path']).stat().st_size==row['bytes']
        artifacts[name]=ref(row['path'])
    assert sha(portable['manifest']['path'])==portable['manifest']['sha256']
    artifacts['evidence_manifest']=ref(portable['manifest']['path'])
    manifest=dict(schema=4,release='v0.6',passed=True,v06_accepted=True,stable_v1_accepted=False,
        qualified=763,open=0,native_suites=61,raw_native_checks=2157,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        runtime_image=image,host_image=host,coverage=ref(ROOT/'conformance/coverage.json'),
        inventory=ref(ROOT/'conformance/inventory.json'),gate=gate,repository_tests=totals,
        evidence={name:ref(path) for name,path in paths.items()},
        artifacts=artifacts,recorder=ref(Path(__file__)),
        scope='Reproducible 0.6.0 native/driver/host/shared packages and JetBrains ZIP; installed Windows hosts; Linux x86_64 GENERIC simulator runtime.',
        supported_platforms=ref(ROOT/'docs/V06_INSTALLATION.md'),
        limitations=[
            'ASan/UBSan diagnostic runtime; leak sanitizer disabled.',
            'No native Windows/macOS, ARM or free-threaded CPython qualification.',
            'Desktop host qualification covers only the exact Windows OpenBEXI, IntelliJ and PyCharm versions in the matrix.',
            'Native service checkpoint resumption remains unsupported.',
            'Operational security, capacity and mission-specific qualification remain v0.7 work; stable v1.0 is not accepted.'])
    target=ROOT/'docs/V06_QUALIFICATION.json'
    if not read(target).get('v06_accepted'):
        (ROOT/'distribution/evidence/pre-v06-qualification.json').write_bytes(target.read_bytes())
    target.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,release='v0.6',qualified=763,output=str(target))))


if __name__=='__main__':
    main()
