"""Derive source expectations from independently reviewed native captures.

This does not accept the combined build. Both complete diagnostic families must
pass before their retained installed bytes can become composition expectations.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from limit_features_review import review as limit_review
from telemetry_features_review import review as telemetry_review

sha=lambda content:hashlib.sha256(content).hexdigest()


def committed_record(identity):
    assert set(identity)=={'commit','path','sha256'}
    commit=subprocess.check_output(['git','rev-parse',identity['commit']],cwd=ROOT,text=True).strip()
    assert commit==identity['commit'] and len(commit)==40
    content=subprocess.check_output(['git','show',commit+':'+identity['path']],cwd=ROOT)
    assert sha(content)==identity['sha256']
    return json.loads(content)


def retained_raw(report):
    path=Path(report['raw']['path'])
    content=path.read_bytes()
    assert sha(content)==report['raw']['sha256']
    raw=json.loads(content)
    assert report['passed'] and raw['passed'] and raw['runtime_image']==report['runtime_image']
    assert not raw['timed_out'] and raw['controller_exit_code']==0
    assert all(row['passed'] for row in raw['checks'].values())
    return path,raw


def apply(python,driver,composition,identities):
    assert set(identities)=={'limit_features','limit_manual','telemetry_features'}
    reports={name:committed_record(identity) for name,identity in identities.items()}
    raw={}
    combined=set()
    for name,count in (('limit_features',48),('limit_manual',16)):
        report=reports[name]
        path,item=retained_raw(report);raw[name]=item
        assert len(item['checks'])==count and not combined.intersection(item['checks'])
        combined.update(item['checks'])
        fresh=limit_review(path,Path(report['overlay']),report['source_revision'],report['runtime_image'],list(item['checks']))
        assert fresh['checks']==report['checks']
    from limit_features_cases import CASES
    assert combined==set(CASES) and len(combined)==64
    first,second=(raw[name]['runtime_sources'] for name in ('limit_features','limit_manual'))
    assert first==second
    report=reports['telemetry_features']
    path,item=retained_raw(report);raw['telemetry_features']=item
    assert len(item['checks'])==32
    fresh=telemetry_review(path,Path(report['overlay']),Path(report['limit_overlay']),report['source_revision'],report['runtime_image'])
    assert fresh['checks']==report['checks']
    # Every recipe is replayed again by these independent reviewers. The maps
    # below take expected bytes from those captures, never from today's output.
    for name,recipe in (('limit_features',composition.limit_feature_patches),
                        ('telemetry_features',composition.telemetry_feature_patches)):
        report=reports[name];item=raw[name];runtime=item['runtime_sources']
        path='source_port/'+Path(recipe.__file__).name
        frozen=subprocess.check_output(['git','show',report['source_revision']+':'+path],cwd=ROOT)
        assert sha(frozen)==item['inputs'][path]
        assert frozen.replace(b'\r\n',b'\n')==(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        manifest=runtime['overlay']['manifest']
        assert set(manifest)==set(recipe.PREIMAGES)
        for source,row in manifest.items():
            mapping=python if source.startswith('spell/') else driver
            assert mapping[source]==row['preimage_sha256']==recipe.PREIMAGES[source]
            assert runtime['installed'][source]==row['sha256']
            mapping[source]=row['sha256']
        # Keep every source outside these changes bound to the preceding donor.
        for mapping in (python,driver):
            for source,digest in mapping.items():
                assert runtime['installed'][source]==digest
    return identities
