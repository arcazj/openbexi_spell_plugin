"""Run v0.4 acceptance with installed wheels and copied tests, without source imports."""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import platform
import subprocess
import pytest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ide',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,required=True)
    parser.add_argument('--image',required=True,help='Exact audited native DSS image SHA256')
    parser.add_argument('--wheels',type=Path,required=True,help='JSON map: distribution name to exact path/sha256')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    helper = Path(__file__).resolve().parents[1]/'distribution/workflow_evidence.py'
    spec = importlib.util.spec_from_file_location('workflow_evidence',helper)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    image = evidence.exact_image(args.image)
    assert subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True).strip()==image
    assert sys.version_info[:2]==(3,13) and platform.python_implementation()=='CPython'
    bindings = json.loads(args.wheels.read_bytes())
    assert set(bindings)=={'openbexi-ide','openbexi-spell-shared','openbexi-spell-host','openbexi-spell-dss','openbexi-spell-plugin'}
    installed = evidence.installed_wheels(bindings,args.wheels.resolve().parent)
    os.environ['OPENBEXI_NATIVE_TEST_IMAGE'] = image
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ.pop('PYTEST_ADDOPTS',None)
    assert importlib.metadata.version('pytest')=='8.4.2'
    owners = {'openbexi_runtime':'openbexi-ide','openbexi_spell_shared':'openbexi-spell-shared',
        'openbexi_spell_host':'openbexi-spell-host','openbexi_spell_dss':'openbexi-spell-dss','dss':'openbexi-spell-plugin'}
    imports = evidence.imported_modules(bindings,owners,args.wheels.resolve().parent)
    origins = {name:row['origin'] for name,row in imports.items()}
    assert importlib.util.find_spec('PySide6') is None
    tests = root/'tests'
    tests.mkdir()
    ide_tests = ['native_driver_acceptance.py','test_shared_backends.py',
                 'test_sessions.py','test_durable_sessions.py','test_execution_sessions.py']
    plugin_tests = ['test_original_driver.py','kafka_driver_acceptance.py']
    for repository,names in ((args.ide,ide_tests),(args.plugin,plugin_tests)):
        for name in names:
            shutil.copy2(repository/'tests'/name,tests/name)
    oracle = Path(__file__).resolve().parents[1]/'distribution/installed_driver_oracles.py'
    oracle_spec = importlib.util.spec_from_file_location('installed_driver_oracles', oracle)
    oracle_module = importlib.util.module_from_spec(oracle_spec)
    oracle_spec.loader.exec_module(oracle_module)
    assert importlib.metadata.version('openbexi-spell-dss') == '0.6.0'
    original_tests = root/'original-tests'
    original_tests.mkdir()
    for name in ('native_driver_acceptance.py','test_original_driver.py'):
        shutil.copy2(tests/name, original_tests/name)
        (tests/name).write_text(oracle_module.adapt(name,(tests/name).read_text(encoding='utf-8')),
                               encoding='utf-8',newline='\n')
    test_inputs = {name:evidence.sha(tests/name) for name in ide_tests+plugin_tests}
    source_inputs = {str((repository/'tests'/name).resolve()):evidence.sha(repository/'tests'/name)
        for repository,names in ((args.ide,ide_tests),(args.plugin,plugin_tests)) for name in names}
    # This prior accepted binding must survive the provider upgrade.
    from openbexi_spell_shared import validate,PROFILE
    validate(dict(profile=PROFILE,version='0.4.0.dev1',image='sha256:'+'a'*64))
    (root/'pytest.ini').write_text('[pytest]\n',encoding='utf-8')
    code = pytest.main([str(tests/name) for name in (
        'native_driver_acceptance.py','test_shared_backends.py','test_original_driver.py','kafka_driver_acceptance.py')]
        + ['-q','-c',str(root/'pytest.ini'),'--junitxml='+str(root/'tests.xml')])
    assert installed==evidence.installed_wheels(bindings,args.wheels.resolve().parent)
    assert imports==evidence.imported_modules(bindings,owners,args.wheels.resolve().parent)
    assert all(evidence.sha(tests/name)==digest for name,digest in test_inputs.items())
    assert all(evidence.sha(name)==digest for name,digest in source_inputs.items())
    result = dict(passed=code==0,python=sys.version,origins=origins,
        image=image,platform=platform.platform(),prefix=sys.prefix,
        installed_wheels=installed,imported_modules=imports,test_inputs=test_inputs,source_inputs=source_inputs,
        harness_sha256=evidence.sha(Path(__file__)),auditor_sha256=evidence.sha(helper),
        installed_oracle_sha256=evidence.sha(oracle),
        original_tests={name:evidence.sha(original_tests/name) for name in
                        ('native_driver_acceptance.py','test_original_driver.py')},
        wheel_inputs=evidence.reference(args.wheels),full_v06_accepted=False,
        packages=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()],key=lambda r:r['name']),
        old_development_binding_accepted=True)
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
