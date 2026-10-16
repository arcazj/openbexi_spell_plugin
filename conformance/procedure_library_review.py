"""Reconcile native library resolution, child modes and original build inputs."""
import hashlib,json,sys,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from evidence_sources import source_bytes
from installed_provenance import verify_capture

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))
encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'))
SELECTED={
 'file-identifier':('child','child#0'), 'header-name':('alias','actual_file#0'),
 'nested-file':('Bus','Bus/procedure#0'), 'default-folder-order':('Bus','Bus/procedure#0'),
 'configured-priority':('Validation','Validation/procedure#0'), 'configured-override':('Bus','Bus/procedure#0'),
 'configured-name-priority':('Validation','Validation/procedure#0'),
 'hidden-blocking':('hidden','child#0'), 'hidden-nonblocking':('hidden','child#0'),
 'hidden-manual':('hidden','child#0'), 'complex-visible-manual':('manual','child#0'),
 'missing-then-nested':('Bus','Bus/procedure#0'),
}


def frozen(name,revision):
    module=types.ModuleType('_procedure_review_'+Path(name).stem)
    exec(compile(source_bytes(ROOT,name,revision),name,'exec'),module.__dict__)
    return module


def overlay_proof(raw,directory,revision):
    runtime=raw['runtime_sources'];assert runtime['profile']=='fresh-composed-wheel-plus-procedure-library-overlay/1'
    assert sha(directory/'base.json')==runtime['base_sha256']
    base=read(directory/'base.json');assert base['profile']=='fresh-composed-display-command-wheel/1'
    assert base['integrated']==runtime['integrated'];verify_capture(runtime['integrated'],raw['inputs'])
    overlay=runtime['overlay'];record=read(directory/'build.json');assert record==overlay['build']
    assert record['passed'] is True and record['original_link_reproduced'] is True
    assert overlay['files']=={p.relative_to(directory).as_posix():sha(p) for p in directory.rglob('*')
        if p.is_file() and p.name!='base.json' and '__pycache__' not in p.parts}
    for name,path in (('procedure_library_patches.py','source_port/procedure_library_patches.py'),
                      ('procedure_library_build.py','conformance/procedure_library_build.py'),
                      ('procedure_library_provenance.py','conformance/procedure_library_provenance.py')):
        assert sha(directory/name)==raw['inputs'][path]
    recipe=frozen('source_port/procedure_library_patches.py',revision)
    assert sha(directory/'original-child.C')==record['original_child_sha256']==recipe.PREIMAGES[recipe.SOURCE]
    assert recipe.apply(recipe.SOURCE,(directory/'original-child.C').read_bytes())==(directory/'patched-child.C').read_bytes()
    assert sha(directory/'patched-child.C')==record['patched_child_sha256']
    assert record['recipe_sha256']==sha(directory/'procedure_library_patches.py')
    expected=dict(base['installed']);library='spell_native/bin/libspell_executor313.so'
    assert record['donor_runtime_sha256']==expected[library]
    assert record['runtime_sha256']!=record['donor_runtime_sha256']
    expected[library]=record['runtime_sha256']
    assert set(record['modules'])=={'spell_native/launcher.py','spell_native/library.py'}
    for name,digest in record['modules'].items():
        assert sha(directory/Path(name).name)==digest==raw['inputs']['source_port/distribution/'+Path(name).name]
        expected[name]=digest
    assert runtime['installed']==expected


def review(raw_path,overlay,revision,image):
    raw=read(raw_path);workspace=raw_path.parent/'workspace'
    assert raw['passed'] is True and raw['controller_exit_code']==0 and raw['timed_out'] is False
    assert raw['runtime_image']==image and set(raw['checks'])==set(SELECTED)
    for name,digest in raw['inputs'].items():assert hashlib.sha256(source_bytes(ROOT,name,revision)).hexdigest()==digest,name
    assert raw['artifacts']=={p.relative_to(workspace).as_posix():sha(p) for p in workspace.rglob('*') if p.is_file()}
    assert read(workspace/'checks.json')==raw['checks'] and read(workspace/'runtime.json')==raw['runtime_sources']
    overlay_proof(raw,overlay,revision)
    cases=frozen('conformance/procedure_library_cases.py',revision).CASES
    checks={}
    for name,row in raw['checks'].items():
        project=workspace/name;spec=cases[name];label,instance=SELECTED[name]
        assert row['passed'] is True and row['parent_status']=='FINISHED' and not any(k.endswith('_error') for k in row)
        assert row['source']==spec['parent']==(project/'main.py').read_text(encoding='utf-8')
        assert row['files']==spec['files']
        for path,source in spec['files'].items():assert (project/path).read_text(encoding='utf-8')==source
        expected={'selected':label,'arguments':{'A':1,'B':False,'C':''} if name=='complex-visible-manual' else {}}
        assert encode(read(project/'child-result.json'))==encode(row['child_result'])==encode(expected)
        assert encode(read(project/'parent-result.json'))==encode(row['parent_result'])==encode({'returned':True})
        assert read(project/'child-started.json')=={'started':True}
        assert row['configuration']==spec['configuration']
        if spec['configuration'] is None:assert not (project/'spell-library.json').exists()
        else:assert read(project/'spell-library.json')==spec['configuration']
        assert set(row['child_info'])=={instance}
        info=row['child_info'][instance]
        assert info['ProcId']==instance and info['ParentId']=='main#1'
        assert info['OpenMode']=='{Automatic:%s,Visible:%s,Blocking:%s}'%(spec['automatic'],spec['visible'],spec['blocking'])
        if name=='header-name':assert info['ProcName']=='Friendly Procedure'
        if name=='configured-name-priority':assert info['ProcName']=='Shared Procedure'
        assert any(instance in inventory for inventory in row['inventories'])
        if spec['automatic']:
            assert row['controls']==[] and row['manual_observations']==[]
        else:
            assert row['controls']==[{'instance':instance,'command':'CMD_RUN'}]
            assert len(row['manual_observations'])==3
            for value in row['manual_observations']:
                assert value['instance']==instance and value['status']=='PAUSED'
                assert value['child_started'] is False and value['parent_returned'] is (not spec['blocking'])
        assert ('rejected' in row) is spec['rejection']
        if spec['rejection']:assert row['rejected']==read(project/'rejected.json')=={'rejected':True}
        assert sha(project/'native.log')==row['native_log_sha256']
        log=(project/'native.log').read_text(encoding='utf-8')
        assert not any(text in log for text in ('AddressSanitizer:','runtime error:','Exception in thread'))
        assert sha(project/'events.json')==row['events_sha256']
        events=read(project/'events.json')
        assert not any(e.get('event') in ('connectionError','unsupportedRequest','childRequestRejected') or
                       e.get('message',{}).get('id') in ('MSG_PROMPT','MSG_ERROR') for e in events)
        checks[name]=dict(passed=True,contracts=[],selected_child=expected,native_instance=instance,
            oracle='Literal child identity and arguments, original inventory and modes, actual paused observations before manual start, rejection recovery, exact retained source/build artifacts')
    inputs=dict(raw['inputs']);inputs['conformance/procedure_library_review.py']=sha(ROOT/'conformance/procedure_library_review.py')
    return dict(passed=True,runtime_image=image,raw=ref(raw_path),overlay=str(overlay.resolve()),source_revision=revision,
        checks=checks,inputs=inputs,qualified_contracts=[],full_v05_accepted=False,full_v06_accepted=False,
        scope='Twelve independent native library/mode diagnostics; whole FLOW mapping and composed runtime gates remain required')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--raw',type=Path,required=True);parser.add_argument('--overlay',type=Path,required=True)
    parser.add_argument('--revision',required=True);parser.add_argument('--image',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=review(args.raw,args.overlay,args.revision,args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,checks=len(result['checks']),output=str(args.output))))
