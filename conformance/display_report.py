"""Draft strict display diagnostic report; install after frozen native capture."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'distribution'), str(ROOT/'source_port'), str(ROOT/'driver_plugin/src')]
from display_cases import CASES
from display_baseline_cases import CASES as BASELINE_CASES
from evidence_sources import source_bytes
from run_language_regressions import validate_report
from installed_provenance import verify_capture
import display_patches
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p

DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
DEPENDENCIES = {
    'CONSTANT-PRINT-FORMAT-PS': ('printing','printer','timespan'),
    'CONSTANT-PRINT-FORMAT-VECTOR': ('printing','printer'),
    'EXAMPLE-119': ('lifecycle',), 'EXAMPLE-120': ('workspace',),
    'EXAMPLE-121': ('routing',), 'EXAMPLE-122': ('routing',), 'EXAMPLE-123': ('timespan',),
    'EXAMPLE-124': ('printer',), 'EXAMPLE-125': ('printing',),
    'EXAMPLE-126': ('lifecycle',), 'EXAMPLE-127': ('workspace',),
    'FUNCTION-OPENDISPLAY': ('lifecycle','routing','reuse','timespan'),
    'FUNCTION-CLOSEDISPLAY': ('lifecycle','routing','reuse'),
    'FUNCTION-OPENWORKSPACE': ('workspace','routing','reuse'),
    'FUNCTION-CLOSEWORKSPACE': ('workspace','routing','reuse'),
    'FUNCTION-PRINTDISPLAY': ('printing','printer','timespan'),
    'MODIFIER-HOST': ('routing',), 'MODIFIER-MONITOR': ('routing',),
    'MODIFIER-PRINTER': ('printer',), 'MODIFIER-REUSE': ('reuse',),
    'SECTION-4-13-086': ('lifecycle','workspace','routing','reuse','timespan','printing','printer'),
    'SECTION-4-13-1-087': ('lifecycle','workspace','routing','reuse','timespan'),
    'SECTION-4-13-2-088': ('printing','printer','timespan'),
    'SECTION-4-13-3-089': ('lifecycle','workspace','routing','reuse'),
}
CANDIDATES = ['CMP-LRM244-' + name for name in DEPENDENCIES]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()),sha256=sha(path))
canonical = lambda value: json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def verify_observation(observation):
    ground, telemetry = observation['ground'], observation['telemetry']
    snapshots = ground.get('display_snapshots', {})
    for key, snapshot in snapshots.items():
        assert hashlib.sha256(canonical(snapshot)).hexdigest() == key
        assert snapshot == telemetry
    apps = ground['display_applications']
    assert len(apps) <= 16
    for key, app in apps.items():
        assert key == app['id'] and int(key) > 0
        assert app['host'] in ('DSS','DSS_AUX') and type(app['monitor']) is int and app['monitor'] in (1,2)
        assert app['displays']
        for name, row in app['displays'].items():
            assert name in ('DSS_TELEMETRY','DSS_TREND','Displays/Telemetría')
            assert row['kind'] == ('plot' if name == 'DSS_TREND' else 'alphanumeric')
            assert row['snapshot_sha256'] in snapshots
            assert type(row['span_seconds']) in (int,float) and 0 < row['span_seconds'] <= 86400
    jobs = ground['display_jobs']
    assert len(jobs) <= 64
    for key, job in jobs.items():
        assert key == job['id'] and int(key) > 0
        assert job['snapshot_sha256'] in snapshots and job['content'].isascii()
        assert job['status'] == ('SPOOLED' if job['printer'] else 'FILE')
        assert job['printer'] in ('','DSS_REPORTS') and job['host'] in ('DSS','DSS_AUX')
        assert job['display'] in ('DSS_TELEMETRY','DSS_TREND','Displays/Telemetría')
        if job['format'] == 'VECTOR':
            assert job['display'] != 'DSS_TREND' and job['media_type'] == 'text/plain'
            rows = job['content'].splitlines()
            assert rows[0] == ('DISPLAY\t' + job['display']).encode('ascii','backslashreplace').decode()
            assert rows[1].split('\t') == ['ITEM','ENGINEERING','VALIDITY','ACQUIRED_UNIX_NS']
            expected = [[str(sample['item_id']),str(sample['engineering']['value']),str(sample['validity']),
                         str(sample['acquired_at_unix_ns'])] for sample in telemetry['samples']]
            assert [line.split('\t') for line in rows[2:]] == [
                [value.encode('ascii','backslashreplace').decode() for value in row] for row in expected]
        else:
            assert job['format'] == 'PS' and job['media_type'] == 'application/postscript'
            assert job['content'].startswith('%!PS-Adobe-3.0\n') and job['content'].endswith('%%EOF\n')
            assert '%%Page: 1 1\n' in job['content'] and 'showpage\n' in job['content']
            if job['display'] == 'DSS_TREND':
                assert 'arc fill' in job['content'] and 'lineto stroke' in job['content']
                assert ('Initial time span: %.6f seconds' % job['span_seconds']) in job['content']


def verify_cases(path,image,source_revision=None):
    raw=read(path)
    validate_report(path,image,len(CASES),source_revision=source_revision)
    assert raw['passed'] and raw['controller_exit_code']==0 and not raw.get('timed_out')
    assert set(raw['checks'])==set(CASES) and len(CASES)==35
    assert not raw['qualified_contracts'] and raw['diagnostic_only']
    verify_capture(raw['runtime_sources']['integrated'],raw['inputs'])
    workspace=path.parent/'workspace'
    assert raw['artifacts']=={p.relative_to(workspace).as_posix():sha(p) for p in workspace.rglob('*') if p.is_file()}
    assert read(workspace/'procedure/checks.json')==raw['checks']
    assert read(workspace/'procedure/cases.json')==CASES
    for name in ('display_controller.py','display_provenance.py','installed_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    assert sha(workspace/'procedure/display_contracts.py')==raw['inputs']['conformance/display_contracts.py']
    assert (workspace/'procedure/main.py').read_bytes()==b'import display_contracts\ndisplay_contracts.run()\n'
    assert read(workspace/'runtime.json')==raw['runtime_sources']
    assert read(workspace/'host-inputs.json')==raw['host_inputs']
    assert raw['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    controller=read(workspace/'controller-result.json');assert controller==raw['controller']
    assert controller['passed'] and controller['status']=='FINISHED'
    assert not any(key.endswith('_error') for key in controller)
    for key in ('rpc','events','observations','native_log'):
        name='native.log' if key=='native_log' else key+'.json'
        assert sha(workspace/name)==controller[key+'_sha256']
    log=(workspace/'native.log').read_text(encoding='utf-8')
    assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
    assert not any(row.get('event')=='connectionError' or row.get('message',{}).get('id')=='MSG_PROMPT'
                   for row in read(workspace/'events.json'))
    rpc=read(workspace/'rpc.json');observations=read(workspace/'observations.json')
    checks={}
    counts={'timespan:positive':1,'printing:positive':2,'printing:boundary':64,'printing:failure':1,
            'printing:encoding':2,'printer:positive':1,'printer:boundary':2,'printer:failure':1,
            'printer:encoding':2,'printing:recovery':2,'printer:recovery':2}
    for name,spec in CASES.items():
        row=raw['checks'][name]
        assert row['passed'] and all(row[key]==value for key,value in spec.items())
        observed=[item for item in observations if item['check']==name]
        assert observed[0]['command']['action']=='reset' and observed[0]['response']==row['before']
        assert observed[-1]['command']['action']=='observe' and observed[-1]['response']==row['after']
        assert row['before']['ground']['display_applications']==row['before']['ground']['display_jobs']=={}
        assert row['after']['ground']['display_applications']=={}
        assert len(row['after']['ground']['display_jobs'])==counts.get(name,0)
        for item in observed:
            answer=item['response']
            if 'ground' in answer:
                verify_observation(answer)
            elif 'artifact' in answer:
                artifact=(workspace/answer['artifact']).resolve()
                assert artifact.is_relative_to(workspace.resolve())
                assert sha(artifact)==answer['sha256']
                text=answer['html' if item['command']['action']=='viewer' else 'content']
                assert artifact.read_bytes()==text.encode('utf-8')
        successful=[item for item in rpc if item['check']==name and 'response' in item
                    and item['path'].startswith('/spell.driver.SPELLDriverInterface_TASK/')]
        native_success=[item for item in row['calls'] if 'returned' in item]
        effects=row['after']['effects'][len(row['before']['effects']):]
        assert len(successful)==len(native_success)==len(effects)>0
        for wire,native,effect in zip(successful,native_success,effects):
            assert native['returned'] is True and native['return_type']=='bool'
            method=native['function'].replace('Workspace','Display')
            assert wire['path'].endswith('/'+method) and wire['response']==''
            request=p.Display.FromString(bytes.fromhex(wire['request']))
            assert request.name==native['target']
            config=unpack(request.config)
            workspace_call=native['function'].endswith('Workspace')
            assert config.get('_OpenBEXIWorkspace',False) is workspace_call
            assert set(config)==set(native['options'])|({'_OpenBEXIWorkspace'} if workspace_call else set())
            for key,value in native['options'].items():
                if key=='Time':
                    assert type(config[key]) in (int,float) and 0<config[key]<=86400
                else:
                    assert str(config[key])==value
            assert effect['state']=='RECEIPTED' and effect['request_id']==wire['request_id']
            assert effect['receipt']==wire['response']
            assert effect['digest']==hashlib.sha256(wire['path'].encode()+b'\0'+bytes.fromhex(wire['request'])).hexdigest()
        assert all(item['state']=='RECEIPTED' for item in row['after']['effects'])
        if spec['dimension'] in ('failure','recovery'):
            assert any('error_type' in item for item in row['calls'])
        if spec['dimension']=='recovery':
            reopens=[item for item in observed if item['command']['action']=='reopen']
            assert reopens
            assert any('error' in item and item['check']==name and item['started']<int(reopens[0]['command']['token'])/1e9 for item in rpc)
            assert any(item['started']>int(reopens[0]['command']['token'])/1e9 for item in successful)
        checks[name]=dict(deepcopy(row),contracts=[],oracle='Actual native helpers, original binary RPC, persistent journal, independently read DSS telemetry and HTTP-downloaded documents')
    return raw,checks


def qualify(path,baseline_path,image,overlay,baseline_revision):
    raw,checks=verify_cases(path,image)
    baseline=read(baseline_path)
    assert not baseline['passed'] and not baseline['timed_out'] and len(baseline['checks'])==4
    assert set(baseline['checks'])==set(BASELINE_CASES)
    assert baseline['runtime_sources']['integrated']==raw['runtime_sources']['integrated']
    assert read(baseline_path.parent/'workspace/checks.json')==baseline['checks']
    for name,digest in baseline['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT,name,baseline_revision)).hexdigest()==digest,name
    for name,row in baseline['checks'].items():
        assert not row['passed'] and row['source']==BASELINE_CASES[name]['source']
        assert read(baseline_path.parent/'workspace'/name/'observed.json')==row['observed']
    surface=baseline['checks']['api-surface']['observed']
    assert surface['functions']=={'OpenWorkspace':False,'CloseWorkspace':False}
    assert surface['formats']=={'PS':None,'VECTOR':None}
    assert surface['modifiers']=={'Monitor':None,'Reuse':None}
    calls=baseline['checks']['display-lifecycle']['observed']['calls']
    assert calls[0]['function']=='OpenDisplay' and calls[0].get('returned') is None
    assert calls[1]['function']=='CloseDisplay' and calls[1].get('returned') is not True
    for name in ('display-options','print-vector'):
        assert any('error' in item for item in baseline['checks'][name]['rpc'])
    runtime=raw['runtime_sources'];record=runtime['overlay']
    assert runtime['profile']=='fresh-wheel-plus-declared-display-overlay/1'
    assert record['files']=={item.relative_to(overlay).as_posix():sha(item)
                            for item in overlay.rglob('*') if item.is_file() and item.name!='base.json'}
    for name in ('display_provenance.py','installed_provenance.py','display.Dockerfile'):
        assert record['files'][name]==inputs_value(raw,'conformance/'+name)
    assert record['files']['display_patches.py']==inputs_value(raw,'source_port/display_patches.py')
    assert sha(overlay/'base.json')==runtime['base_sha256']
    base=read(overlay/'base.json');assert base['integrated']==runtime['integrated']
    assert read(overlay/'manifest.json')==record['manifest']
    expected=dict(base['installed']);sources={}
    assert set(record['manifest'])==set(display_patches.PREIMAGES)
    for name,item in record['manifest'].items():
        original=overlay/'original'/name;patched=overlay/'patched'/name
        assert expected[name]==item['preimage_sha256']==sha(original)
        assert display_patches.apply(name,original.read_bytes())==patched.read_bytes()
        expected[name]=sha(patched);assert item['sha256']==expected[name]
        sources[name]=dict(original=ref(original),patched=ref(patched))
    assert set(record['added_sources'])=={'openbexi_spell_dss/displays.py','openbexi_spell_dss/display_viewer.py'}
    for name,digest in record['added_sources'].items():
        assert name not in expected
        expected[name]=digest
        assert sha(overlay/'modules'/name)==digest==raw['inputs']['driver_plugin/src/'+name]
    assert runtime['installed']==expected
    inputs=dict(raw['inputs'])
    for name in ('conformance/display_report.py','tests/test_display_report.py'):
        inputs[name]=sha(ROOT/name)
    for short,groups in DEPENDENCIES.items():
        contract='CMP-LRM244-'+short
        for dimension in DIMENSIONS:
            dependencies=[group+':'+dimension for group in groups]
            encoding_checks=[group+':encoding' for group in groups]
            assert all(checks[key]['passed'] for key in dependencies+encoding_checks)
            checks[contract+':'+dimension]=dict(passed=True,dimension=dimension,contracts=[contract],dependencies=dependencies,
                encoding_checks=encoding_checks,oracle='All required native family leaves plus Unicode/format encoding checks')
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,raw=ref(path),baseline=ref(baseline_path),
        baseline_revision=baseline_revision,source_files=sources,overlay_manifest=ref(overlay/'manifest.json'),
        overlay_base=ref(overlay/'base.json'),runtime_sources=runtime,candidate_contracts=CANDIDATES,qualified_contracts=[],
        scope='Diagnostic GENERIC display application; fresh composed native/driver packages and complete regressions remain required',
        exclusions=['Physical workstation/printer completion','Broader Format modifier','Broader Time modifier'],
        full_v05_accepted=False,full_v06_accepted=False)


def inputs_value(raw,name):
    return raw['inputs'][name]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path);parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--image',required=True);parser.add_argument('--overlay',type=Path,required=True)
    parser.add_argument('--baseline-revision',required=True)
    args=parser.parse_args()
    result=qualify(args.raw,args.baseline,args.image,args.overlay,args.baseline_revision)
    target=ROOT/'conformance/evidence/display.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(target),candidate_contracts=len(CANDIDATES),qualified_contracts=[])))
