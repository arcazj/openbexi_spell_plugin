"""Independently review native database files, frozen procedures and sources."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'distribution'),str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from installed_provenance import verify_capture
from telemetry_features_review import provenance as telemetry_provenance

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def frozen(name,revision):
    source=source_bytes(ROOT,name,revision)
    module=types.ModuleType('_database_format_review_'+Path(name).stem)
    if name.endswith('/database_values_cases.py'):
        anchor=b'from database_import_cases import GROUND, SPACECRAFT'
        assert source.count(anchor)==1
        previous=frozen('conformance/database_import_cases.py',revision)
        module.GROUND,module.SPACECRAFT=previous.GROUND,previous.SPACECRAFT
        source=source.replace(anchor,b'')
    exec(compile(source,name,'exec'),module.__dict__)
    return module


def overlay_proof(raw,overlay,telemetry,limits,revision):
    runtime=raw['runtime_sources']
    assert runtime['profile']=='fresh-composed-limit-telemetry-database-format-overlays/1'
    assert sha(overlay/'base.json')==runtime['base_sha256']
    base=read(overlay/'base.json')
    assert base['integrated']==runtime['integrated']
    # The database capture predates explicit binding of this installed resource.
    # Bind it independently to the frozen commit and retained parent overlay;
    # keep that expectation distinct from the original capture's input map.
    resource='driver_plugin/src/openbexi_spell_dss/limit_files/normal.json'
    expected_resource=hashlib.sha256(source_bytes(ROOT,resource,revision)).hexdigest()
    assert sha(limits/'modules/openbexi_spell_dss/limit_files/normal.json')==expected_resource
    parent_inputs=dict(raw['inputs'])
    assert resource not in parent_inputs or parent_inputs[resource]==expected_resource
    parent_inputs[resource]=expected_resource
    telemetry_provenance(dict(runtime_sources=base,inputs=parent_inputs),telemetry,limits,revision)
    record=runtime['overlay']
    assert record['files']=={p.relative_to(overlay).as_posix():sha(p) for p in overlay.rglob('*')
        if p.is_file() and p.name!='base.json' and '__pycache__' not in p.parts}
    recipe=frozen('source_port/database_format_patches.py',revision)
    assert sha(overlay/'database_format_patches.py')==raw['inputs']['source_port/database_format_patches.py']
    assert read(overlay/'manifest.json')==record['manifest'] and set(record['manifest'])==set(recipe.PREIMAGES)
    expected=dict(base['installed'])
    for name,row in record['manifest'].items():
        before,after=overlay/'original'/name,overlay/'patched'/name
        assert sha(before)==row['preimage_sha256']==recipe.PREIMAGES[name]==expected[name]
        assert recipe.apply(name,before.read_bytes())==after.read_bytes()
        expected[name]=sha(after);assert expected[name]==row['sha256']
    assert runtime['installed']==expected


def literal(node):
    # Independent data-only parser: never execute the runtime's importer.
    if isinstance(node,ast.Call):
        assert isinstance(node.func,ast.Name) and node.func.id=='TIME'
        assert len(node.args)==1 and not node.keywords
        value=ast.literal_eval(node.args[0]);assert type(value) is str
        return ('TIME',value)
    if isinstance(node,ast.List):return [literal(v) for v in node.elts]
    if isinstance(node,ast.Dict):return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
    return ast.literal_eval(node)


def records(content):
    result=[]
    for line in content.decode('utf-8').splitlines():
        key,value=line.split('\t',1)
        try:key=ast.literal_eval(key)
        except (ValueError,SyntaxError):assert key.isidentifier()
        result.append((type(key).__name__,key,literal(ast.parse(value,mode='eval').body)))
    return result


EXPECTED={
 'keys-positive':[('int',42,'integer'),('float',2.5,'float'),('int',255,'hex'),('int',29,'octal'),('int',41,'binary')],
 'keys-boundary':[('int',0,'zero'),('int',-17,'negative'),('int',1208925819614629174706176,'large'),
     ('float',0.25,'fraction'),('str','42','numeric text'),('str','two spaces','spaced key'),('str','2007/01/23 10:30','date text')],
 'keys-failure':[('str','KEY',42)],
 'keys-recovery':[('str','KEY',42),('int',17,'recovered')],
 'nested-time-positive':[('str','VALUES',{'items':[('TIME','2007-01-23 10:30:00.123456'),
     {'relative':('TIME','+2 03:04:05.000006')}],'plain':[False,0,'two  spaces']})],
 'nested-time-boundary':[('str','VALUES',[[],{},('TIME','-0 00:00:00.000001'),('TIME','+0 00:00:00.000000'),
     {'literal':"TIME('not a timestamp')"}])],
 'nested-time-failure':[('str','KEY',42)],
 'nested-time-recovery':[('str','KEY',42),('str','VALUES',[('TIME','+0 00:00:35.000000')])],
}


def archive_proof(raw,files,revision):
    suite=raw['suite']
    casefile={'formats':'database_format_cases.py','user':'user_database_cases.py','values':'database_values_cases.py'}[suite]
    controller={'formats':'database_format_controller.py','user':'user_database_controller.py','values':'database_values_controller.py'}[suite]
    catalog=frozen('conformance/'+casefile,revision);cases=catalog.CASES
    assert len(cases)=={'formats':8,'user':20,'values':24}[suite]
    assert json.loads(files['checks.json'])==raw['checks'] and set(raw['checks'])==set(cases)
    assert json.loads(files['runtime.json'])==raw['runtime_sources'] and json.loads(files['cases.json'])==cases
    assert json.loads(files['example.json'])==(catalog.EXAMPLE if suite=='user' else None)
    original=source_bytes(ROOT,'conformance/'+controller,revision).decode().replace('\r\n','\n')
    generated=original.replace('from database_values_provenance import capture','from database_format_provenance import capture') if suite=='values' else original.replace('from installed_provenance import capture','from database_format_provenance import capture')
    if suite!='values':
        start=generated.index('report=dict(installed=installed,manifest=');end=generated.index('\n',start)
        generated=generated[:start]+'report=capture()'+generated[end:]
    assert files['controller.py']==generated.encode() and hashlib.sha256(files['controller.py']).hexdigest()==raw['generated_controller_sha256']
    for name in ('user_database_prompts.py','database_format_provenance.py','installed_provenance.py'):
        assert hashlib.sha256(files[name]).hexdigest()==raw['inputs']['conformance/'+name]
    tree=ast.parse(original);target='code' if suite=='values' else 'prelude'
    assignment,=[node for node in ast.walk(tree) if isinstance(node,ast.Assign)
        and any(isinstance(v,ast.Name) and v.id==target for v in node.targets)]
    if suite=='values':prefix=ast.literal_eval(assignment.value.left.left);suffix=ast.literal_eval(assignment.value.right)
    else:
        prefix=ast.literal_eval(assignment.value)+('EXAMPLE='+repr(catalog.EXAMPLE if suite=='user' else '')+'\n')
        suffix="\nDisplay('"+('USER_DATABASE_PASSED' if suite=='user' else 'DATABASE_FORMAT_PASSED')+"')\n"
    checks={}
    for name,spec in cases.items():
        row=raw['checks'][name];assert row['passed'] is True and all(row[k]==v for k,v in spec.items())
        project=name.replace(':','-')
        assert files[project+'/data/Procedures/main.py'].decode()==prefix+spec['source']+suffix
        log=files[project+'/native.log']
        assert b'[ STATUS  ] FINISHED' in log and all(s not in log for s in (b'AddressSanitizer:',b'runtime error:'))
        assert ('CONFIGURED_DATABASE_PASSED' if suite=='values' else 'USER_DATABASE_PASSED' if suite=='user' else 'DATABASE_FORMAT_PASSED').encode() in log
        result=dict(passed=True,dimension=spec.get('dimension','regression'))
        if suite=='formats':
            actual=records(files[project+'/data/User/MyData/data.IMP'])
            assert json.dumps(actual)==json.dumps(EXPECTED[name]),name
            assert not any(n.startswith(project+'/data/User/MyData/.spell-db-') for n in files)
            result['persisted']=actual
        checks[name]=result
    if suite=='user':
        assert json.loads(files['prompts.json'])==raw['prompts'] and set(raw['prompts'])=={'prompt-abort','prompt-rename'}
        for mode,count,status in [('abort',1,'ABORTED'),('rename',2,'FINISHED')]:
            prompt=raw['prompts']['prompt-'+mode]
            expected={'existing.IMP':'SAVED 42\n'}
            if mode=='rename':expected['renamed.IMP']='KEY\t7\n'
            assert prompt['passed'] is True and prompt['mode']==mode and prompt['status']==status
            assert len(prompt['prompts'])==count and prompt['files']==expected
            for filename,content in expected.items():
                matches=[v for k,v in files.items() if k.startswith('prompt-'+mode+'/') and k.endswith('/'+filename)]
                assert matches==[content.encode()]
    else:assert raw['prompts']=={}
    return checks


def review(paths,overlay,telemetry,limits,revision,image):
    assert set(paths)=={'formats','user','values'}
    checks={};references={};archives={};sources=None
    for suite,path in paths.items():
        raw=read(path)
        assert raw['suite']==suite and raw['runtime_image']==image and raw['controller_exit_code']==0
        for name,value in raw['inputs'].items():
            content=source_bytes(ROOT,name,revision)
            assert hashlib.sha256(content).hexdigest()==value
            assert hashlib.sha256(content.replace(b'\r\n',b'\n')).hexdigest()==raw['lf_normalized_inputs'][name]
        verify_capture(raw['runtime_sources']['integrated'],raw['inputs'],raw['lf_normalized_inputs'])
        overlay_proof(raw,overlay,telemetry,limits,revision)
        assert sources is None or sources==raw['runtime_sources'];sources=raw['runtime_sources']
        with tarfile.open(path.parent/'workspace.tar') as archive:
            entries=[v for v in archive.getmembers() if v.isfile()]
            files={v.name.removeprefix('./'):archive.extractfile(v).read() for v in entries}
            assert len(files)==len(entries)
        checks.update({suite+':'+name:row for name,row in archive_proof(raw,files,revision).items()})
        references[suite]=ref(path);archives[suite]=ref(path.parent/'workspace.tar')
    assert len(checks)==52
    return dict(passed=True,runtime_image=image,source_revision=revision,raw=references,archives=archives,
        overlay=str(overlay.resolve()),telemetry_overlay=str(telemetry.resolve()),limit_overlay=str(limits.resolve()),
        checks=checks,review_source=ref(Path(__file__)),source_inputs=raw['inputs'],
        reviewed_parent_inputs={'driver_plugin/src/openbexi_spell_dss/limit_files/normal.json':
            hashlib.sha256(source_bytes(ROOT,'driver_plugin/src/openbexi_spell_dss/limit_files/normal.json',revision)).hexdigest()},
        qualified_contracts=[],full_v05_accepted=False)
