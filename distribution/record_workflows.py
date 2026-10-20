"""Record fresh host or installed-driver workflows without historical defaults.

Consumes a JSON map of named {path, sha256} references. Does not launch Docker,
install packages, infer unobserved platforms or accept the complete release.
"""
import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
import workflow_evidence as proof
import build_images as builder


def require(condition, message):
    if not condition:
        raise ValueError(message)


def counts(path):
    document = ET.parse(path).getroot()
    result = {key:sum(int(row.get(key,0)) for row in document.iter('testsuite'))
              for key in ('tests','failures','errors','skipped')}
    require(result['tests']>0 and not any(result[k] for k in ('failures','errors','skipped')),
            'JUnit has failures, skips or no tests')
    require(len(list(document.iter('testcase')))==result['tests'],'JUnit testcase count differs')
    return result


def checked_report(path, image=None):
    result = proof.load(path)
    require(result.get('passed') is True, 'Workflow did not pass: '+str(path))
    if image is not None:
        require(result.get('image')==image, 'Workflow used a different image: '+str(path))
    return result


def foundation(paths, image):
    proof.exact_image(image)
    build = checked_report(paths['image_build'])
    pair = checked_report(paths['native_pair'])
    require(build['driver_plugin']['image']==image, 'Selected image is not the audited fresh DSS image')
    expected_checks = {'independent_native_rebuilds','native_artifacts_identical','python_sources_identical',
        'composition_identical','wheel_bytes_identical','fresh_install_and_removal'}
    require(set(pair['checks'])==expected_checks and all(pair['checks'].values()),'Independent native pair incomplete')
    require(pair['toolchain_image']==build['toolchain'],'Toolchain identity differs')
    pair_root, build_root = paths['native_pair'].parent, paths['image_build'].parent
    pair_inputs = pair_root/'inputs.json'
    require(proof.sha(pair_inputs)==pair['inputs_sha256'],'Native snapshot input manifest changed')
    for name,digest in proof.load(pair_inputs).items():
        require(proof.sha(pair_root/'source'/name)==digest,'Native snapshot changed: '+name)
        if name.startswith('source_port/') or name.startswith('docs/reference/') or (
                name.startswith('distribution/') and Path(name).suffix in {'.py','.Dockerfile','.lock'}):
            require(proof.sha(ROOT/name)==digest,'Native build input is stale: '+name)
    inputs = build_root/'inputs.json'
    require(proof.sha(inputs)==build['inputs_sha256'],'Image snapshot input manifest changed')
    for name,digest in proof.load(inputs).items():
        require(proof.sha(build_root/'source'/name)==digest,'Image snapshot changed: '+name)
        if name.startswith(('host_runtime/','distribution/')) or (
                name.startswith('driver_plugin/') and (ROOT/name).is_file() and not name.endswith('.py')):
            require(proof.sha(ROOT/name)==digest,'Image build input is stale: '+name)
    native = builder.inspect_wheel(paths['native_wheel'],require_composition=True)
    driver = builder.inspect_wheel(paths['driver_wheel'],require_driver_composition=True)
    require(native==build['native_wheel'] and driver==build['driver_wheel'],'Selected wheel differs from fresh image inputs')
    require(len(pair['packages'])==2 and all(p['sha256']==native['sha256'] for p in pair['packages']),
            'Native wheel is not the independently reproduced artifact')
    audit_path = build_root/'installed-record.json'
    require(proof.sha(audit_path)==build['installed_record_sha256'],'Installed image audit changed')
    audit = checked_report(audit_path)
    require(audit['native_artifacts']==native['native_artifacts'] and audit['composition']==native['composition'],
            'Installed native image payload differs')
    require(audit['driver_composition']['manifest']==driver['driver_composition']['manifest'],
            'Installed driver payload differs')
    builder.verify_host_sources(ROOT/'host_runtime/python',audit['host_sources'])
    with tempfile.TemporaryDirectory(prefix='spell-driver-recorder-') as directory:
        site = Path(directory)/'src'
        shutil.copytree(ROOT/'driver_plugin/src',site,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
        expected = builder.apply_driver_tree(site,site/'openbexi_dss_proxy/_composition')
    require(expected==driver['driver_composition']['manifest'],'Fresh driver differs from current checked source composition')
    return dict(image=image,host_image=build['host_runtime']['image'],toolchain=build['toolchain'],
        native_wheel=native,driver_wheel=driver,installed_audit=proof.reference(audit_path))


def pipe_report(path, platform, wheel):
    data = checked_report(path)
    require(data['harness_sha256']==proof.sha(ROOT/'scripts/qualify_host_input.py'),'Pipe harness changed')
    require(data['original_tests_sha256']==proof.sha(ROOT/'host_plugin/tests/test_runner_input.py'),'Pipe oracles changed')
    require(data['expected_platform']==platform and data['installed']['platform']==platform,'Pipe platform differs')
    require(data['installed']['wheel_sha256']==wheel['sha256'] and data['installed']['installed_members']==wheel['members'],
            'Pipe tests exercised different installed wheel bytes')
    require(data['tests']==dict(tests=16,failures=0,errors=0,skipped=0) and data['exit_code']==0,'Pipe cases incomplete')
    original = (path.parent/'original_test_runner_input.py').read_bytes()
    require(hashlib_sha(original)==data['original_tests_sha256'],'Retained pipe oracle differs')
    site = (PureWindowsPath if platform=='Windows' else PurePosixPath)(data['installed']['package_origin']).parent.parent
    anchor = "HOST_SOURCE = Path(__file__).resolve().parents[1] / 'src'"
    text = original.decode('utf-8')
    require(text.count(anchor)==1,'Retained pipe oracle anchor differs')
    expected = text.replace(anchor,'HOST_SOURCE = Path('+repr(str(site))+')').encode('utf-8')
    require((path.parent/'test_runner_input.py').read_bytes()==expected and
        hashlib_sha(expected)==data['adapted_tests_sha256'],'Installed pipe import adaptation differs')
    actual_files = {p.relative_to(path.parent).as_posix():proof.sha(p) for p in path.parent.rglob('*')
                   if p.is_file() and p.resolve()!=path.resolve()}
    require(data['evidence_files']==actual_files,'Pipe evidence inventory differs')
    for name,digest in data['evidence_files'].items():
        require(proof.sha(path.parent/name)==digest,'Pipe evidence changed: '+name)
    require(counts(path.parent/'tests.xml')==data['tests'],'Pipe JUnit differs')
    return data


def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def verifier_report(path, workflow, product_code, plugin_sha256):
    data = checked_report(path)
    require(data['harness_sha256']==proof.sha(ROOT/'distribution/qualify_plugin_verifier.py'),'Verifier harness changed')
    require(data['exit_code']==0 and data['plugin_sha256']==plugin_sha256,'Verifier result/artifact differs')
    require(data['sdk']==workflow['sdk'] and data['sdk']['productCode']==product_code and
        data['sdk_metadata_sha256']==workflow['sdk_metadata_sha256'],'Verifier SDK/product identity differs')
    metadata=Path(data['sdk_path'])/'product-info.json'
    require(proof.sha(metadata)==data['sdk_metadata_sha256'],'Verifier SDK metadata changed')
    inputs={name:proof.bound_file(row,path.parent) for name,row in data['inputs'].items()}
    require(set(inputs)=={'java','verifier','plugin'} and proof.sha(inputs['plugin'])==plugin_sha256,'Verifier inputs differ')
    expected=[str(inputs['java']),'-jar',str(inputs['verifier']),'check-plugin',str(inputs['plugin']),
        data['sdk_path'],'-verification-reports-dir',str(path.parent/'reports')]
    require(data['command']==expected,'Verifier invocation differs from selected artifacts')
    with zipfile.ZipFile(inputs['verifier']) as archive:
        version=[line.split(':',1)[1].strip() for line in archive.read('META-INF/MANIFEST.MF').decode().splitlines()
                 if line.startswith('Verifier-Version:')]
    require(version==[data['verifier_version']],'Verifier tool version differs')
    actual={p.relative_to(path.parent).as_posix():proof.sha(p) for p in path.parent.rglob('*')
            if p.is_file() and p.resolve()!=path.resolve()}
    require(data['evidence_files']==actual,'Verifier output inventory changed')
    verdict=(path.parent/data['verdict']['path']).resolve()
    require(verdict.is_relative_to(path.parent.resolve()) and proof.sha(verdict)==data['verdict']['sha256'] and
        verdict.read_text(encoding='utf-8').startswith('Compatible.'),'Verifier verdict is absent or incompatible')
    return data


def import_proof(imports, owners, artifacts):
    require(set(imports)==set(owners),'Executed import proof is incomplete')
    for name,distribution in owners.items():
        row=imports[name]
        expected=artifacts[distribution]
        require(row['distribution']==distribution and row['wheel_sha256']==expected['sha256'] and
            row['member']==name.replace('.','/')+'/__init__.py' and
            expected['members'].get(row['member'])==row['sha256'],'Executed import is not the selected wheel member: '+name)


def host(paths, image, ide):
    wheel = proof.wheel_source(paths['host_wheel'],ROOT/'host_plugin/src')
    ide_wheel = proof.wheel_source(paths['ide_wheel'],ide/'src')
    for name,number,harness in [('adapter',14,'qualify_host_adapter.py'),('child_prompts',2,'qualify_child_prompts.py')]:
        data = proof.load(paths[name])
        require(data['image']==image and data['tests']==number and data['failures']==data['errors']==0,'Native host cases failed/mixed')
        require(data['inputs'].get('scripts/'+harness)==proof.sha(ROOT/'scripts'/harness),'Native host harness is unbound')
        proof.source_inputs(data['inputs'],ROOT)
        for source in (ROOT/'host_runtime/python').glob('*.py'):
            require(data['inputs'].get(source.relative_to(ROOT).as_posix())==proof.sha(source),'Native host source missing')
    lifecycle = checked_report(paths['lifecycle'],image)
    require(lifecycle['script_sha256']==proof.sha(ROOT/'scripts/qualify_host_lifecycle.py') and
        lifecycle['installed_auditor_sha256']==proof.sha(ROOT/'scripts/qualify_host_input.py'),'Lifecycle harness changed')
    require(lifecycle['installed_host']['wheel_sha256']==wheel['sha256'] and
        lifecycle['installed_host']['installed_members']==wheel['members'],'Lifecycle host wheel differs')
    require(len(lifecycle['checks'])==3 and len(lifecycle['runtime_instances'])==3 and
        {r['mode'] for r in lifecycle['runtime_instances']}=={'cli','eof','process-tree-loss'} and
        all(r['image']==image for r in lifecycle['runtime_instances']),'Lifecycle image/phase proof incomplete')
    platforms = {name:pipe_report(paths[key],name,wheel) for name,key in [('Windows','windows_pipe'),('Linux','linux_pipe')]}
    upgrade = checked_report(paths['upgrade'],image)
    require(upgrade['harness_sha256']==proof.sha(ROOT/'scripts/qualify_host_upgrade.py'),'Upgrade harness changed')
    require(upgrade['qt_interpreter']['system']=='Windows' and
        upgrade['qt_interpreter']['implementation']=='CPython' and upgrade['qt_interpreter']['python'].startswith('3.13.'),
        'Source Qt upgrade has a different platform/interpreter profile')
    require(upgrade['wheel_sha256']==wheel['sha256'] and upgrade['previous_wheel_sha256']==proof.sha(paths['previous_host_wheel']),
            'Upgrade artifacts differ')
    require(upgrade['installed_wheel_members']==wheel['members'] and len(upgrade['checks'])==4,'Upgrade installed payload/checks incomplete')
    require(upgrade['ide_source_inputs']=={p.relative_to(ide).as_posix():proof.sha(p) for p in (ide/'src').rglob('*.py')},
            'Qt source IDE differs from qualification')
    desktop = checked_report(paths['openbexi'],image)
    require(desktop['wrapper_sha256']==proof.sha(ROOT/'distribution/openbexi_workflows.py') and
        desktop['original_harness_sha256']==proof.sha(ROOT/'scripts/qualify_openbexi_host.py'),'Installed IDE harness changed')
    require(desktop['host_wheel_sha256']==wheel['sha256'] and desktop['ide_wheel_sha256']==proof.sha(paths['ide_wheel']),
            'Installed IDE workflow artifacts differ')
    require(desktop['installed_auditor_sha256']==proof.sha(ROOT/'distribution/workflow_evidence.py') and
        desktop['installed_ide']=={'openbexi-ide':dict(**ide_wheel,installed_members_verified=len(ide_wheel['members']))},
        'Installed IDE payload proof differs')
    underlying = paths['openbexi'].parent/desktop['result']
    require(proof.sha(underlying)==desktop['result_sha256'],'Installed IDE result changed')
    actual = checked_report(underlying)
    require(actual['runtime_images']==[image] and actual['checks']==desktop['checks'],'Installed IDE runtime proof differs')
    require(actual['installed_ide_imports']==desktop['installed_ide_imports'],'Installed IDE imported origins differ')
    import_proof(actual['installed_ide_imports'],{'openbexi_ide':'openbexi-ide','openbexi_runtime':'openbexi-ide'},
        {'openbexi-ide':ide_wheel})
    adapted = paths['openbexi'].parent/'source/scripts/qualify_openbexi_host.py'
    require(proof.sha(adapted)==desktop['adapted_harness_sha256'],'Installed IDE adapted harness changed')
    build = proof.load(paths['jetbrains_build'])
    require(build['sha256']==proof.sha(paths['jetbrains_zip']),'JetBrains build artifact differs')
    proof.source_inputs(build['inputs'],ROOT/'jetbrains')
    for name,product_code in [('pycharm','PY'),('intellij','IU')]:
        data = checked_report(paths[name],image)
        require(data['wrapper_sha256']==proof.sha(ROOT/'distribution/host_workflows.py'),'JetBrains wrapper changed')
        proof.source_inputs(data['original_sources'],ROOT/'jetbrains')
        expected_sources = {p.relative_to(ROOT/'jetbrains').as_posix():proof.sha(p)
            for p in (ROOT/'jetbrains').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
        require(data['original_sources']==expected_sources,'JetBrains source snapshot is incomplete')
        proof.source_inputs(data['harness_sources'],paths[name].parent/'source/jetbrains')
        require(data['installed_auditor_sha256']==proof.sha(ROOT/'scripts/qualify_host_input.py') and
            data['installed_host']['wheel_sha256']==wheel['sha256'] and
            data['installed_host']['installed_members']==wheel['members'],'JetBrains installed host differs')
        require(data['plugin_sha256']==build['sha256'],'JetBrains workflow artifact differs')
        for phase in ('installed','removed'):
            selected = paths[name].parent/data[phase]['result']
            require(proof.sha(selected)==data[phase]['sha256'],'JetBrains phase report changed')
            child = checked_report(selected)
            require(child['runtime_images']==[image] and child['plugin_sha256']==build['sha256'] and child['checks'],
                    'JetBrains phase identity differs')
            require(child['sdk']=={key:data['sdk'][key] for key in ('name','version','buildNumber')} and
                data['sdk']['productCode']==product_code,'JetBrains product or phase SDK differs')
        verifier_report(paths[name+'_verifier'],data,product_code,build['sha256'])
    return dict(host_wheel=wheel,pipe_platforms={name:row['installed'] for name,row in platforms.items()},
        scope='Exact installed host, native DAP/lifecycle, Windows source Qt upgrade, installed Qt, IntelliJ/PyCharm workflows and declared pipe platforms; no browser or complete release acceptance')


def driver(paths,image,ide):
    data = checked_report(paths['driver_installed'],image)
    require(data['harness_sha256']==proof.sha(ROOT/'scripts/qualify_driver_installed.py') and
        data['auditor_sha256']==proof.sha(ROOT/'distribution/workflow_evidence.py'),'Installed driver harness changed')
    artifacts = {'openbexi-ide':('ide_wheel',ide/'src'),
        'openbexi-spell-host':('host_wheel',ROOT/'host_plugin/src'),
        'openbexi-spell-shared':('shared_wheel',ROOT/'shared_plugin/src'),
        'openbexi-spell-plugin':('service_wheel',ROOT/'src'),
        'openbexi-spell-dss':('driver_wheel',None)}
    require(set(data['installed_wheels'])==set(artifacts),'Installed distribution set differs')
    for name,(key,source) in artifacts.items():
        expected = proof.wheel_source(paths[key],source) if source else proof.wheel(paths[key])[0]
        actual = data['installed_wheels'][name]
        require(actual==dict(**expected,installed_members_verified=len(expected['members'])),'Installed artifact differs: '+name)
    import_proof(data['imported_modules'],{'openbexi_runtime':'openbexi-ide','openbexi_spell_host':'openbexi-spell-host',
        'openbexi_spell_shared':'openbexi-spell-shared','openbexi_spell_dss':'openbexi-spell-dss','dss':'openbexi-spell-plugin'},
        data['installed_wheels'])
    source_tests = {name:repository/'tests'/name for repository,names in (
        (ide,['native_driver_acceptance.py','test_shared_backends.py','test_sessions.py','test_durable_sessions.py','test_execution_sessions.py']),
        (ROOT,['test_original_driver.py','kafka_driver_acceptance.py'])) for name in names}
    from installed_driver_oracles import adapt
    import hashlib
    expected_tests = {name:hashlib.sha256(adapt(name,path.read_text(encoding='utf-8')).encode()).hexdigest()
                      if name in ('native_driver_acceptance.py','test_original_driver.py') else proof.sha(path)
                      for name,path in source_tests.items()}
    require(data['installed_oracle_sha256']==proof.sha(ROOT/'distribution/installed_driver_oracles.py'),
            'Installed contract adapter changed')
    for name in ('native_driver_acceptance.py','test_original_driver.py'):
        require(data['original_tests'][name]==proof.sha(source_tests[name]),'Original integration test changed')
        require(proof.sha(paths['driver_installed'].parent/'original-tests'/name)==proof.sha(source_tests[name]),
                'Retained original integration test changed')
    require(data['test_inputs']==expected_tests,'Installed driver copied tests differ')
    for name,digest in expected_tests.items():
        require(proof.sha(paths['driver_installed'].parent/'tests'/name)==digest,'Copied driver oracle changed')
    require(data['old_development_binding_accepted'] is True,'Prior provider binding compatibility absent')
    junit = paths['driver_installed'].parent/'tests.xml'
    result = counts(junit)
    require(result['tests']>=48,'Installed driver gate lost previously required cases')
    observed = {row.get('classname','').split('.')[-1] for row in ET.parse(junit).iter('testcase')}
    require(observed=={'native_driver_acceptance','test_shared_backends','test_original_driver','kafka_driver_acceptance'},
            'Installed driver test families incomplete')
    return dict(tests=result,installed=data['installed_wheels'],scope='Selected installed wheel set and complete unfiltered native/shared/original-driver/Kafka test families; no complete release or remote-broker security acceptance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=('host','driver'),required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--image',required=True)
    parser.add_argument('--ide',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    inputs = proof.load(args.evidence)
    paths = {name:proof.bound_file(value,args.evidence.resolve().parent) for name,value in inputs.items()}
    runtime = foundation(paths,args.image)
    result = (host if args.kind=='host' else driver)(paths,args.image,args.ide.resolve())
    report = dict(schema='openbexi.spell.fresh-workflows/1',kind=args.kind,passed=True,
        runtime=runtime,qualification=result,evidence={name:proof.reference(path) for name,path in paths.items()},
        input_manifest=proof.reference(args.evidence),recorder_sha256=proof.sha(__file__),
        helper_sha256=proof.sha(ROOT/'distribution/workflow_evidence.py'),
        full_v05_accepted=False,full_v06_accepted=False,qualified_contracts=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:
        output.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output),sha256=proof.sha(args.output),kind=args.kind,passed=True)))


if __name__=='__main__':
    main()
