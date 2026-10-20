"""Recorder/parser checks only; synthetic records make no runtime claims."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from checkpoint_identity_provenance import EXPECTED_SOURCES,qualification_identity
from checkpoint_identity_report import ERRORS, MODES, REQUIRED_INPUTS, integrated_gates, qualify_run
from installed_provenance import PROFILE, input_paths


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.inputs={'host_runtime/python/native.py':sha(ROOT/'host_runtime/python/native.py')}
        recipes={}
        stages=[]
        names={'SPELLcontext.C':'checkpoint_context_patches.py',
            'SPELLinterpreter.C':'checkpoint_identity_patches.py','SPELLframeManager.C':'checkpoint_error_patches.py'}
        for source,row in EXPECTED_SOURCES.items():
            recipe=names[Path(source).name]
            digest=sha(ROOT/'source_port'/recipe)
            self.inputs['source_port/'+recipe]=digest
            recipes[recipe]=dict(sha256=digest,lf_sha256=digest)
            stages.append(dict(recipe=recipe,sources={source:dict(before_sha256=row['ported_sha256'],
                after_sha256=row['patched_sha256'])}))
        self.record=dict(profile=PROFILE,manifest_sha256='parser-fixture',python_sources={},
            native_artifacts={'libspell_executor313.so':'runtime','SPELL-Context':'context',
                'SPELL-ExecutorCmd_v3':'command','SPELL-Executor_v3':'executor',
                'SPELL-Service_v3':'service','SPELL-Listener':'listener'},
            host_native_sha256=self.inputs['host_runtime/python/native.py'],
            manifest={'composition':{'native':dict(sources=copy.deepcopy(EXPECTED_SOURCES),
                recipes=recipes,stages=stages)}})

    def test_current_installed_source_identity(self):
        identity=qualification_identity(self.record,self.inputs)
        self.assertEqual(identity['kind'],'installed-composition')
        self.assertEqual(identity['native_artifacts'],self.record['native_artifacts'])

    def snapshot_fixture(self):
        sys.path.insert(0,str(ROOT/'source_port'))
        import native_patches,checkpoint_error_patches,trace_read_patches
        name='lib/SPELL_EXC/src/SPELLframeManager.C'
        with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as bundle:
            original=bundle.read(name)
        checkpoint=checkpoint_error_patches.apply(name,original,native_patches.apply(name,original),fix=True)
        final=hashlib.sha256(trace_read_patches.apply(name,original,checkpoint)).hexdigest()
        native=self.record['manifest']['composition']['native']
        digest=sha(ROOT/'source_port/trace_read_patches.py')
        self.inputs['source_port/trace_read_patches.py']=digest
        native['recipes']['trace_read_patches.py']=dict(sha256=digest,lf_sha256=digest)
        native['sources'][name]['patched_sha256']=final
        native['stages'].append(dict(recipe='trace_read_patches.py',sources={name:dict(
            before_sha256=hashlib.sha256(checkpoint).hexdigest(),after_sha256=final)}))
        return name,final

    def test_exact_checkpoint_then_snapshot_chain(self):
        from checkpoint_error_provenance import qualification_identity as error_identity
        name,final=self.snapshot_fixture()
        for verify in (qualification_identity,error_identity):
            self.assertEqual(verify(self.record,self.inputs)['kind'],'installed-composition')
            for mutation in ('missing','before','after','unbound','checkpoint'):
                with self.subTest(verifier=verify.__module__,mutation=mutation):
                    record=copy.deepcopy(self.record)
                    native=record['manifest']['composition']['native']
                    if mutation=='missing':native['stages'].pop()
                    elif mutation=='before':native['stages'][-1]['sources'][name]['before_sha256']='wrong'
                    elif mutation=='after':
                        native['stages'][-1]['sources'][name]['after_sha256']='wrong'
                        native['sources'][name]['patched_sha256']='wrong'
                    elif mutation=='unbound':del native['recipes']['trace_read_patches.py']
                    else:
                        next(stage for stage in native['stages']
                             if stage['recipe']=='checkpoint_error_patches.py')['recipe']='trace_read_patches.py'
                    with self.assertRaises(ValueError):verify(record,self.inputs)
        identity=qualification_identity(self.record,self.inputs)
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);self.gate_fixture(directory)
            path=directory/'executor-build.json';build=json.loads(path.read_bytes())
            next(row for row in build['units'] if row['unit']==name)['sha256']=final
            path.write_text(json.dumps(build))
            context_path=directory/'context-build.json';context=json.loads(context_path.read_bytes())
            context['executor_build_sha256']=sha(path);context_path.write_text(json.dumps(context))
            integrated_gates(directory,identity)

    def current_runner_fixture(self):
        names=set(REQUIRED_INPUTS)|set(input_paths(ROOT))|{'host_runtime/python/native.py'}
        names.update('conformance/'+name for name in (
            'ipc_mailbox_provenance.py','ipc_mailbox_build.py','ipc_mailbox_race.cpp',
            'ipc_mailbox_install.py','ipc_mailbox.Dockerfile','context_snapshot.Dockerfile',
            'context_snapshot_build.py','context_snapshot_install.py',
            'context_snapshot_probe.py','context_snapshot_provenance.py'))
        return dict(controller_exit_code=0,
            options=dict(cases=list(ERRORS),modes=list(MODES),kind='error-ipc'),
            checks={mode+':'+case:dict(passed=True,mode=mode,case=case)
                for mode in MODES for case in ERRORS},
            runtime_sources=copy.deepcopy(self.record),
            inputs={name:sha(ROOT/name) for name in names})

    def test_current_runner_context_snapshot_inputs_accepted(self):
        identity=qualify_run(self.current_runner_fixture(),ERRORS,'error-ipc')
        self.assertEqual(identity['kind'],'installed-composition')

    def test_partial_context_snapshot_inputs_rejected(self):
        report=self.current_runner_fixture()
        del report['inputs']['conformance/context_snapshot_probe.py']
        with self.assertRaises(AssertionError):qualify_run(report,ERRORS,'error-ipc')

    def test_unknown_runner_input_rejected(self):
        report=self.current_runner_fixture()
        report['inputs']['conformance/unrecognized.py']='0'*64
        with self.assertRaises(AssertionError):qualify_run(report,ERRORS,'error-ipc')

    def test_changed_context_snapshot_input_rejected(self):
        report=self.current_runner_fixture()
        report['inputs']['conformance/context_snapshot_probe.py']='0'*64
        with self.assertRaises(AssertionError):qualify_run(report,ERRORS,'error-ipc')

    def test_missing_or_changed_sources_and_recipes(self):
        for source in EXPECTED_SOURCES:
            for mutation in ('missing','changed','recipe'):
                with self.subTest(source=source,mutation=mutation):
                    record=copy.deepcopy(self.record);native=record['manifest']['composition']['native']
                    if mutation=='missing':del native['sources'][source]
                    elif mutation=='changed':native['sources'][source]['patched_sha256']='wrong'
                    else:
                        recipe=next(s['recipe'] for s in native['stages'] if source in s['sources'])
                        del native['recipes'][recipe]
                    with self.assertRaises(ValueError):qualification_identity(record,self.inputs)

    def test_missing_broken_or_relabelled_stage(self):
        for mutation in ('missing','broken','relabelled','duplicate'):
            with self.subTest(mutation=mutation):
                record=copy.deepcopy(self.record);native=record['manifest']['composition']['native']
                if mutation=='missing':del native['stages']
                elif mutation=='broken':next(iter(native['stages'][0]['sources'].values()))['before_sha256']='wrong'
                elif mutation=='duplicate':native['stages'].append(copy.deepcopy(native['stages'][0]))
                else:native['stages'][0]['recipe']='checkpoint_error_patches.py'
                with self.assertRaises(ValueError):qualification_identity(record,self.inputs)

    def test_wrong_recipe_input_or_host_rejected(self):
        for name in self.inputs:
            with self.subTest(name=name):
                inputs=dict(self.inputs);inputs[name]='wrong'
                with self.assertRaises(ValueError):qualification_identity(self.record,inputs)
        del self.record['host_native_sha256']
        with self.assertRaises(ValueError):qualification_identity(self.record,self.inputs)

    def test_historical_overlay_identity_and_runner_recipe_pairs(self):
        recipes={name:sha(ROOT/path) for name,path in (
            ('checkpoint_identity_patches.py','source_port/checkpoint_identity_patches.py'),
            ('checkpoint_context_patches.py','source_port/checkpoint_context_patches.py'),
            ('checkpoint_error_patches.py','source_port/checkpoint_error_patches.py'),
            ('checkpoint_identity_build.py','conformance/checkpoint_identity_build.py'),
            ('incremental_native.py','distribution/incremental_native.py'))}
        inputs=dict(self.inputs,**{'conformance/checkpoint_identity_build.py':recipes['checkpoint_identity_build.py'],
            'distribution/incremental_native.py':recipes['incremental_native.py']})
        original={'libspell_executor313.so':'old-runtime','SPELL-Context':'old-context'}
        overlay=dict(mode='identity',sources=EXPECTED_SOURCES,recipes=recipes,original_artifacts=original,
            artifacts={'libspell_executor313.so':'runtime','SPELL-Context':'context'})
        record=dict(identity_overlay=overlay,baseline={'native_artifacts':original})
        self.assertEqual(qualification_identity(record,inputs)['kind'],'diagnostic-overlay')
        # The actual historical runner's recipe iteration must remain unpackable.
        tree=ast.parse((ROOT/'conformance/checkpoint_error_run.py').read_text())
        loops=[node for node in ast.walk(tree) if isinstance(node,ast.For) and
            isinstance(node.target,ast.Tuple) and [n.id for n in node.target.elts]==['name','path']]
        self.assertEqual(len(loops),1)
        pairs=ast.literal_eval(loops[0].iter)
        self.assertEqual(dict(pairs)['incremental_native.py'],'distribution/incremental_native.py')
        self.assertTrue(all(len(pair)==2 for pair in pairs))

    def gate_fixture(self,directory):
        artifacts=self.record['native_artifacts']
        units=[dict(unit=name,exit_code=0,sha256=row['patched_sha256']) for name,row in EXPECTED_SOURCES.items()]
        executor=dict(qualification_exit_code=0,runtime_sha256=artifacts['libspell_executor313.so'],
            command=dict(sha256=artifacts['SPELL-ExecutorCmd_v3'],link_exit_code=0),
            input_sources={name:sha(ROOT/'source_port'/name) for name in ('qualify_executor.py','executor_build.py')},
            units=[row for row in units if '/SPELL_EXC/' in row['unit']])
        (directory/'executor-build.json').write_text(json.dumps(executor))
        context=dict(qualification_exit_code=0,executor_build_sha256=sha(directory/'executor-build.json'),
            input_sources={name:sha(ROOT/'source_port'/name) for name in ('qualify_context.py','context_build.py')},programs={})
        for program,executable in [('SPELL_Context','SPELL-Context'),('SPELL_Listener','SPELL-Listener'),
                ('SPELL_Executor_v3','SPELL-Executor_v3'),('SPELL_Service_v3','SPELL-Service_v3')]:
            context['programs'][program]=dict(link_exit_code=0,sha256=artifacts[executable],executable=executable,
                units=[row for row in units if '/SPELL_CTX/' in row['unit']])
        for name,tests in [('executor',23),('context',10)]:
            (directory/(name+'-runtime.json')).write_text(json.dumps(dict(tests=tests,failures=0,errors=0,skips=0,
                service_checkpoint_rejections=2,selection='all')))
        (directory/'context-build.json').write_text(json.dumps(context))

    def test_real_gate_format_requires_exact_outputs_sources_and_completion(self):
        identity=qualification_identity(self.record,self.inputs)
        with tempfile.TemporaryDirectory(prefix='checkpoint-recorder-test-') as temporary:
            directory=Path(temporary);self.gate_fixture(directory)
            integrated_gates(directory,identity)
            for file,key,value in [('context-build.json','qualification_exit_code',1),
                    ('context-build.json','executor_build_sha256','wrong'),
                    ('executor-build.json','runtime_sha256','wrong'),
                    ('executor-runtime.json','tests',22),('context-runtime.json','service_checkpoint_rejections',0)]:
                with self.subTest(file=file,key=key):
                    self.gate_fixture(directory)
                    path=directory/file;data=json.loads(path.read_bytes());data[key]=value;path.write_text(json.dumps(data))
                    with self.assertRaises(AssertionError):integrated_gates(directory,identity)


if __name__=='__main__':unittest.main()
