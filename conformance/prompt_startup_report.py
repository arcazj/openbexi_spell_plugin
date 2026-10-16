"""Bind prompt transition fixes to independent source, debugger and native evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

from prompt_startup_provenance import RECIPES, qualification_identity
from prompt_startup_probe import PRELUDE, MAIN, methods
from run_prompt_startup import SUITES, sources_for
from prompt_timeout_cases import CASES as PROMPTS
from child_modes_cases import CASES as MODES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import child_lifecycle_patches
import prompt_timeout_patches
import prompt_control_patches
import prompt_startup_patches as patch

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
digest = lambda raw: hashlib.sha256(raw).hexdigest()
reference = lambda path: dict(path=str(path.resolve()),sha256=sha(path))

def verify_export(directory, runtime):
    overlay = runtime['prompt_startup_overlay']
    base = runtime['baseline']
    assert json.loads((directory / 'manifest.json').read_bytes()) == overlay
    assert json.loads((directory / 'baseline-installed.json').read_bytes()) == base
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    ported = native_patches.apply(patch.SOURCE, original)
    for recipe in (child_lifecycle_patches, prompt_timeout_patches, prompt_control_patches):
        ported = recipe.apply(patch.SOURCE, original, ported)
    patched = patch.apply(patch.SOURCE, original, ported)
    for label, content, field in [('original',original,'original_sha256'),
            ('ported',ported,'preimage_sha256'), ('patched',patched,'patched_sha256')]:
        path = directory / (label + '.C')
        assert path.read_bytes() == content and sha(path) == overlay[field]
    assert overlay['source'] == patch.SOURCE and overlay['passed'] and not overlay['full_release_accepted']
    compiled_path = directory / 'compiled/incremental-build.json'
    assert sha(compiled_path) == overlay['incremental_build_sha256']
    compiled = json.loads(compiled_path.read_bytes())
    assert compiled['passed'] and not compiled['full_qualification_passed']
    assert set(compiled['units']) == {patch.SOURCE}
    unit = compiled['units'][patch.SOURCE]
    assert unit['exit_code'] == 0 and unit['original_sha256'] == patch.PREIMAGES[patch.SOURCE][1]
    assert unit['patched_sha256'] == overlay['patched_sha256']
    assert set(compiled['artifacts']) == set(overlay['artifacts']) == set(overlay['original_artifacts']) == {'libspell_executor313.so'}
    artifact = compiled['artifacts']['libspell_executor313.so']
    assert artifact['exit_code'] == 0
    assert artifact['original_sha256'] == overlay['original_artifacts']['libspell_executor313.so'] == base['native_artifacts']['libspell_executor313.so']
    assert sha(directory / 'compiled/libspell_executor313.so') == artifact['sha256'] == overlay['artifacts']['libspell_executor313.so']
    assert artifact['sha256'] != artifact['original_sha256']
    assert set(overlay['recipes']) == set(RECIPES)
    for name, source in RECIPES.items():
        assert sha(directory / name) == overlay['recipes'][name] == sha(ROOT / source)
    assert compiled['recipe_sha256'] == overlay['recipes']['incremental_native.py']
    probes = overlay['probes']
    assert json.loads((directory / 'probes/result.json').read_bytes()) == probes
    assert sha(directory / 'probes/result.json') == overlay['probes_sha256']
    assert probes['passed'] and probes['preimage_sha256'] == patch.PREIMAGES[patch.SOURCE][1]
    assert probes['patched_sha256'] == overlay['patched_sha256']
    assert set(probes['probes']) == {'original','patched'}
    for label, source in (('original',ported), ('patched',patched)):
        row = probes['probes'][label]
        folder = directory / 'probes'
        probe = folder / (label + '-probe.cpp')
        assert probe.read_text(encoding='utf-8') == PRELUDE + methods(source) + MAIN
        assert sha(probe) == row['source_sha256']
        assert sha(folder / (label + '-probe')) == row['binary_sha256']
        assert json.loads((folder / (label + '-run.log')).read_bytes()) == row['observation']
        assert row['exit_code'] == (1 if label == 'original' else 0)
        assert row['observation'] == {kind:dict(ack_during_transition=label=='patched',
            winner_preserved=True) for kind in ('startup','cancel')}
    return overlay


def verify_run(path, raw, suite):
    assert raw['passed'] and raw['controller_exit_code'] == 0 and raw['suite'] == suite
    assert not any(key.endswith('error') for key in raw)
    archive_path = path.parent / 'workspace.tar'
    assert sha(archive_path) == raw['workspace_sha256']
    _, sources, _ = sources_for(suite)
    assert raw['generated_sources'] == {name:digest(data) for name,data in sources.items()}
    if suite == 'early':
        expected = {f'close-none-{n}' for n in range(40)}
    elif suite in ('lifecycle','removed','reopen'):
        expected = {action+'-'+phase for action in ('close','kill')
                    for phase in (('prompt','finished','none') if suite=='lifecycle' else ('prompt','finished'))}
    elif suite in ('modes','abort'):
        cases = MODES if suite=='modes' else {f'blocking-abort-{n}':MODES['blocking-abort'] for n in range(12)}
        expected = set(cases)
    else:
        cases = PROMPTS if suite=='timeout' else {f'duplicate-{n}:boundary':PROMPTS['duplicate:boundary'] for n in range(24)}
        expected = set(cases)
    assert set(raw['checks']) == expected
    with tarfile.open(archive_path) as archive:
        members = {m.name.removeprefix('./'):m for m in archive if m.isfile()}
        read = lambda name: archive.extractfile(members[name]).read()
        assert all(read(name) == source for name,source in sources.items())
        lifecycle = suite in ('early','lifecycle','removed','reopen')
        if lifecycle:
            observed = json.loads(read('result.json'))
            assert observed == raw['observed'] and observed['passed']
            assert observed['cases'] == raw['checks'] and observed['runtime_sources'] == raw['runtime_sources']
            host = observed['host_inputs']
        else:
            assert json.loads(read('checks.json')) == raw['checks']
            assert json.loads(read('runtime.json')) == raw['runtime_sources']
            host = json.loads(read('host-inputs.json')) if 'host-inputs.json' in members else None
        if host is not None:
            assert host == {Path(name).name: value for name,value in raw['inputs'].items()
                            if name.startswith('host_runtime/python/')}
        for name,row in raw['checks'].items():
            assert row['passed'] and not any(key.endswith('error') or key=='sanitizer_failure' for key in row)
            folder = name.replace(':','-') + '/'
            log = read(folder+'native.log')
            if 'native_log_sha256' in row:
                assert digest(log) == row['native_log_sha256']
            assert b'AddressSanitizer:' not in log and b'runtime error:' not in log
            if 'events_sha256' in row:
                assert digest(read(folder+'events.json')) == row['events_sha256']
            if lifecycle:
                for file, expected_hash in row['procedure_inputs'].items():
                    assert digest(read(folder+file)) == expected_hash
                if suite == 'reopen':
                    final = row['checkpoints'][-1]
                    assert final['label']=='both-finished' and row['first_child_id']!=row['second_child_id']
                    assert all(info['ExecutorStatus']=='FINISHED' for info in final['executors'].values())
                    assert final['markers']['parent-finish.txt']==['finished']
                    assert final['markers']['second-start.txt']==['start'] and final['markers']['second-finish.txt']==['finished']
                else:
                    assert row['parent_status']['ExecutorStatus']==row['parent_after_removal']['ExecutorStatus']=='FINISHED'
                    assert json.loads(read(folder+'parent-result.json'))==row['parent_result']
                    if suite=='removed':
                        assert len(row['parent_result'])==2
                        assert all('Child lifecycle request rejected' in r['exception'] for r in row['parent_result'])
                    else:
                        assert row['parent_result']==[{'returned':True},{'returned':True}]
                    assert 'main#1' in row['executor_list']['ExecutorList'].split('\x03')
                    assert row.get('child_id') not in row['executor_list']['ExecutorList'].split('\x03')
            elif suite in ('modes','abort'):
                spec = cases[name]
                assert read(folder+'main.py').decode()==row['source']==spec['parent']
                assert read(folder+'child.py').decode()==row['child_source']==spec['child']
                assert row['parent_result']==spec['expected_parent']
                terminal = row['observations'][-1]
                assert terminal['phase']=='terminal' and terminal['parent_status']=='FINISHED'
                assert terminal['child_status']==spec['outcome']
                if spec['hold']:
                    held=[r for r in row['observations'] if r['phase']=='child-awaiting-input']
                    assert len(held)==3 and all(r['child_status']=='PROMPT' and
                        r['parent_returned'] is (not spec['blocking']) for r in held)
            else:
                spec = cases[name]
                assert read(folder+'main.py').decode()==row['source']==spec['source']
                assert row['status']==spec.get('expected_status','FINISHED')
                if 'answer' in spec:
                    assert json.loads(read(folder+'result.json'))==row['result']
                    assert row['result']['answer']==spec['answer']
                if name.startswith('default:') and name in ('default:positive','default:recovery'):
                    assert row['result']['elapsed']>=.25 and not row['answers']
                if 'minimum_elapsed' in spec:
                    assert row['result']['elapsed']>=spec['minimum_elapsed']
                if suite=='duplicate':
                    assert row['answers']==['1','0'] and len(row['prompts'])==1
    return len(raw['checks'])


def qualify(candidate_path, directory, failure_path, debug_directory, source_revision=None):
    candidate = json.loads(candidate_path.read_bytes())
    assert candidate['passed'] and candidate['state']=='completed' and set(candidate['stages'])==set(SUITES)
    image = candidate['image']
    inputs, counts, raw_refs = {}, {}, {}
    runtime = None
    for suite in SUITES:
        stage = candidate['stages'][suite]
        assert stage['passed'] and stage['exit_code']==0
        path = Path(stage['raw']['path'])
        assert sha(path)==stage['raw']['sha256'] and sha(Path(stage['log']['path']))==stage['log']['sha256']
        raw = json.loads(path.read_bytes())
        assert raw['runtime_image']==image
        if runtime is None: runtime=raw['runtime_sources']
        assert raw['runtime_sources']==runtime
        for name, expected in raw['inputs'].items():
            if name not in inputs:
                content = (ROOT/name).read_bytes() if source_revision is None else subprocess.check_output(
                    ['git','show',source_revision+':'+name],cwd=ROOT)
                assert digest(content)==expected,name
            assert name not in inputs or inputs[name]==expected
            inputs[name]=expected
        qualification_identity(runtime, raw['inputs'])
        counts[suite]=verify_run(path,raw,suite)
        raw_refs[suite]={**reference(path),'workspace_sha256':sha(path.parent/'workspace.tar')}
    assert sum(counts.values())==109
    overlay=verify_export(directory,runtime)
    failure=json.loads(failure_path.read_bytes())
    assert failure['passed'] is False and failure['exit_code']==1
    failed=failure['observed']['cases']['close-none']
    assert not failed['passed'] and 'REQ_EXEC_STATUS: Native reply timed out' in failed['error']
    assert failure['observed']['runtime_sources']==runtime['baseline']
    assert sha(failure_path.parent/'workspace.tar')==failure['workspace_sha256']
    debug_result=debug_directory/'result.json'
    debug=json.loads(debug_result.read_bytes())
    assert not debug['passed'] and not debug['cases']['close-none-10']['passed']
    traces=list((debug_directory/'close-none-10').glob('gdb-*.txt'))
    assert len(traces)==2
    text='\n'.join(path.read_text(encoding='utf-8') for path in traces)
    for symbol in ('SPELLserverCif::processMessage','SPELLipcClientInterface::incomingMessage',
                   'SPELLserverCif::waitAcknowledge','SPELLserverCif::startPrompt','std::mutex::lock'):
        assert symbol in text
    inputs['conformance/prompt_startup_report.py']=sha(Path(__file__))
    inputs['tests/test_prompt_startup_report.py']=sha(ROOT/'tests/test_prompt_startup_report.py')
    return dict(passed=True, runtime_image=image, source=overlay['source'],
        original_sha256=overlay['original_sha256'],preimage_sha256=overlay['preimage_sha256'],
        patched_sha256=overlay['patched_sha256'],recipes=overlay['recipes'],native_artifacts=overlay['artifacts'],
        probes=overlay['probes'],inputs=inputs,passed_checks=counts,raw=raw_refs,candidate=reference(candidate_path),
        export=dict(path=str(directory.resolve()),manifest_sha256=sha(directory/'manifest.json')),
        retained_failure=reference(failure_path),debugger=dict(result=reference(debug_result),
            traces=[reference(path) for path in traces]),qualified_contracts=[],
        scope='Prompt startup and cancellation leave ordered answer/acknowledgement reception available; native lifecycle, timed defaults and first-answer controls',
        limitations=['Diagnostic library overlay; fresh composed packages and full language regressions remain required.'],
        full_v05_accepted=False,full_v06_accepted=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','export','failure','debugger'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    report=qualify(args.candidate,args.export,args.failure,args.debugger)
    output=ROOT/'conformance/evidence/prompt_startup.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),passed=True,checks=report['passed_checks'])))
