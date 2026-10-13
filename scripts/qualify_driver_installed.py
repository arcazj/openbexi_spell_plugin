"""Run v0.4 acceptance with installed wheels and copied tests, without source imports."""
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import pytest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ide',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    modules = ['openbexi_runtime','openbexi_spell_shared','openbexi_spell_host','openbexi_spell_dss','dss']
    origins = {name:str(Path(importlib.import_module(name).__file__).resolve()) for name in modules}
    assert all(Path(path).is_relative_to(Path(sys.prefix).resolve()) for path in origins.values())
    assert importlib.util.find_spec('PySide6') is None
    tests = root/'tests'
    tests.mkdir()
    ide_tests = ['native_driver_acceptance.py','test_shared_backends.py',
                 'test_sessions.py','test_durable_sessions.py','test_execution_sessions.py']
    plugin_tests = ['test_original_driver.py','kafka_driver_acceptance.py']
    for repository,names in ((args.ide,ide_tests),(args.plugin,plugin_tests)):
        for name in names:
            shutil.copy2(repository/'tests'/name,tests/name)
    # This prior accepted binding must survive the provider upgrade.
    from openbexi_spell_shared import validate,PROFILE
    validate(dict(profile=PROFILE,version='0.4.0.dev1',image='sha256:'+'a'*64))
    code = pytest.main([str(tests/name) for name in (
        'native_driver_acceptance.py','test_shared_backends.py','test_original_driver.py','kafka_driver_acceptance.py')]
        + ['-q','--junitxml='+str(root/'tests.xml')])
    result = dict(passed=code==0,python=sys.version,origins=origins,
        packages=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()],key=lambda r:r['name']),
        old_development_binding_accepted=True)
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
