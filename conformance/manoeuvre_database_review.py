"""Independently bind native manoeuvre behavior to retained files and sources."""
import hashlib,json,sys,types
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from evidence_sources import source_bytes
from installed_provenance import verify_capture

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))
encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'))
CONTRACTS=['CMP-LRM244-EXAMPLE-138','CMP-LRM244-SECTION-4-15-2-097']
EXPECTED={
 'load-positive':[42,[0,False,'text'],True,'Part1.IMP'],
 'load-boundary':[0,29,255,'two  spaces'],
 'load-failure':[False,[]],'load-recovery':[7],
 'readonly-positive':[42,True],'readonly-boundary':[[0,False,'text'],False,2],
 'readonly-failure':[True,False],'readonly-recovery':[42,7,7],
}
SEED="KEY 42\nNESTED {'items':[0,False,'text']}\n"


def frozen(name,revision):
    module=types.ModuleType('_manoeuvre_review_'+Path(name).stem)
    exec(compile(source_bytes(ROOT,name,revision),name,'exec'),module.__dict__)
    return module


def overlay_proof(raw,directory,revision):
    runtime=raw['runtime_sources'];assert runtime['profile']=='fresh-composed-wheel-plus-manoeuvre-overlay/1'
    assert sha(directory/'base.json')==runtime['base_sha256']
    base=read(directory/'base.json')
    assert base['profile']=='fresh-composed-display-command-wheel/1' and base['integrated']==runtime['integrated']
    verify_capture(runtime['integrated'],raw['inputs'])
    overlay=runtime['overlay']
    assert overlay['files']=={p.relative_to(directory).as_posix():sha(p) for p in directory.rglob('*')
        if p.is_file() and p.name!='base.json' and '__pycache__' not in p.parts}
    recipe=frozen('source_port/manoeuvre_database_patches.py',revision)
    assert sha(directory/'manoeuvre_database_patches.py')==raw['inputs']['source_port/manoeuvre_database_patches.py']
    assert read(directory/'manifest.json')==overlay['manifest']
    assert set(overlay['manifest'])==set(recipe.PREIMAGES)
    expected=dict(base['installed'])
    for name,row in overlay['manifest'].items():
        before,after=directory/'original'/name,directory/'patched'/name
        assert sha(before)==expected[name]==row['preimage_sha256']
        assert recipe.apply(name,before.read_bytes())==after.read_bytes()
        expected[name]=sha(after);assert expected[name]==row['sha256']
    assert runtime['installed']==expected


def review(raw_path,overlay,revision,image):
    raw=read(raw_path);workspace=raw_path.parent/'workspace'
    assert raw['passed'] is True and raw['controller_exit_code']==0 and raw['timed_out'] is False
    assert raw['runtime_image']==image and set(raw['checks'])==set(EXPECTED)
    for name,digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT,name,revision)).hexdigest()==digest,name
    artifacts={p.relative_to(workspace).as_posix():sha(p) for p in workspace.rglob('*') if p.is_file()}
    assert artifacts==raw['artifacts']
    assert read(workspace/'checks.json')==raw['checks']
    assert read(workspace/'runtime.json')==raw['runtime_sources']
    overlay_proof(raw,overlay,revision)
    old=sys.modules.get('memory_native_cases')
    try:
        sys.modules['memory_native_cases']=frozen('conformance/memory_native_cases.py',revision)
        cases=frozen('conformance/manoeuvre_database_cases.py',revision).CASES
    finally:
        if old is None:sys.modules.pop('memory_native_cases',None)
        else:sys.modules['memory_native_cases']=old
    checks={}
    for name,row in raw['checks'].items():
        project=workspace/name;spec=cases[name]
        assert row['passed'] is True and row['status']=='FINISHED' and not any(k.endswith('_error') for k in row)
        assert row['dimension']==spec['dimension'] and row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
        assert row['states'][-1]['status']=='FINISHED'
        assert encode(row['result'])==encode(read(project/'result.json'))==encode({'completed':True})
        observed=read(project/'observed.json');assert observed==row['observed'] and observed['fixtures']==[]
        values=[v['actual'] for v in observed['observations']]
        assert encode(values)==encode(EXPECTED[name])
        assert all(encode(v['actual'])==encode(v['expected']) for v in observed['observations'])
        assert all(call['return_type']=='ReadOnlyDatabase' for call in observed['calls']
                   if call['function']=='LoadDictionary' and 'returned' in call)
        if name=='load-failure':assert [v['error_type'] for v in observed['calls']]==['DriverException','SyntaxException']
        if name=='load-recovery':assert observed['calls'][0]['error_type']=='DriverException'
        if name=='readonly-failure':
            assert [(v['function'],v.get('error_type')) for v in observed['calls'][1:]]==[
                ('SaveDictionary','DriverException'),('CreateDictionary','DriverException')]
        assert sha(project/'native.log')==row['native_log_sha256']
        log=(project/'native.log').read_text(encoding='utf-8')
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log and 'Exception in thread' not in log
        assert sha(project/'events.json')==row['events_sha256']
        assert not any(e.get('event')=='connectionError' or e.get('message',{}).get('id') in ('MSG_ERROR','MSG_PROMPT') for e in read(project/'events.json'))
        assert row['initial_ground']==row['final_ground'] and row['initial_dss']==row['final_dss']
        assert row['initial_packet_hex']==row['final_packet_hex'] and row['receipts']==[] and row['fixture_controls']==[]
        assert all(call['path']=='/spell.driver.SPELLDriverInterface_EV/RaiseEvent' and 'response' in call for call in row['rpc'])
        configured=ET.parse(project/'context-configured.xml').getroot().findall("databases/location[@name='mmd']")
        assert len(configured)==1 and configured[0].attrib=={'name':'mmd','type':'file','ext':'IMP'} and configured[0].text=='ManeuverDB'
        data=project/'data/mmd/Man01'
        expected_files={} if name=='load-failure' else {'Part1.IMP':SEED}
        if name=='load-boundary':expected_files={'Part1.IMP':'','Part2.custom':"OCTAL 035\nHEX 0xFF\nTEXT 'two  spaces'\n"}
        if name in ('load-recovery','readonly-recovery'):expected_files={'Part1.IMP':'KEY 7\n'}
        assert {p.name:p.read_text(encoding='utf-8') for p in data.iterdir() if p.is_file()}==expected_files
        checks[name]=dict(passed=True,contracts=CONTRACTS,dimension=row['dimension'],observations=values,
            oracle='Original traced manoeuvre reads, rejected writes and reload recovery; literal file contents, detached nested values, native states and unchanged ground verified independently')
    inputs=dict(raw['inputs']);inputs['conformance/manoeuvre_database_review.py']=sha(ROOT/'conformance/manoeuvre_database_review.py')
    return dict(passed=True,runtime_image=image,raw=ref(raw_path),source_revision=revision,overlay=str(overlay.resolve()),
        inputs=inputs,checks=checks,qualified_contracts=CONTRACTS,full_v05_accepted=False,full_v06_accepted=False)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--raw',type=Path,required=True);parser.add_argument('--overlay',type=Path,required=True)
    parser.add_argument('--revision',required=True);parser.add_argument('--image',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=review(args.raw,args.overlay,args.revision,args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,checks=len(result['checks']),output=str(args.output))))
