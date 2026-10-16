"""Bind whole-language reports to a complete, source-verified native sequence."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import SUITES, validate_report

DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
PREFIX = 'CMP-LRM244-'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))


def complete_sequence(path, required, root=ROOT):
    sequence = read(path)
    assert sequence['passed'] is True and sequence['state'] == 'completed'
    assert sequence['complete_sequence'] is True
    assert [s['suite'] for s in sequence['suites']] == [s[0] for s in SUITES]
    assert set(required) <= {s[0] for s in SUITES}
    paths, raws, inputs = {}, {}, {}
    for stage, (_, _, _, minimum) in zip(sequence['suites'], SUITES):
        assert stage['passed'] is True and stage['exit_code'] == 0
        assert ref(Path(stage['log']['path'])) == stage['log']
        raw_path = Path(stage['raw']['path'])
        assert validate_report(raw_path, sequence['image'], minimum, root) == stage['raw']
        if stage['suite'] in required:
            name = stage['suite']; paths[name] = raw_path; raws[name] = read(raw_path)
            for source, digest in raws[name]['inputs'].items():
                assert source not in inputs or inputs[source] == digest, source
                inputs[source] = digest
    inputs['conformance/aggregate_support.py'] = sha(root/'conformance/aggregate_support.py')
    return sequence, paths, raws, inputs


def dimensional_mapping(mapping, reviewed):
    """Each named feature must have independently reviewed evidence in every dimension."""
    checks = {}
    for identifier, dependencies in mapping.items():
        assert dependencies and len(dependencies) == len(set(dependencies))
        for dimension in DIMENSIONS:
            selected = []
            for suite, feature in dependencies:
                key = feature + ':' + dimension
                row = reviewed[suite]['checks'][key]
                assert row['passed'] is True and row['dimension'] == dimension
                selected.append(dict(report=suite, check=key))
            checks[PREFIX+identifier+':'+dimension] = dict(passed=True, dimension=dimension,
                contracts=[PREFIX+identifier], dependencies=selected,
                oracle='Every specified native clause has independently checked actual results, failures and recovery on the same installed runtime.')
    return link_components(checks, reviewed)


def link_components(checks, reviewed):
    """Give the release validator real local dependency keys, retaining provenance.

    A source row was already independently reviewed before this assembler is
    called. Its canonical digest binds the embedded leaf to that review; this
    also lets the ordinary coverage validator propagate a failed leaf.
    """
    for identifier, check in list(checks.items()):
        linked=[]
        for dependency in check.get('dependencies', []):
            if isinstance(dependency,str):
                assert dependency in checks;linked.append(dependency);continue
            assert set(dependency)=={'report','check'}
            kind,name=dependency['report'],dependency['check']
            source=reviewed[kind]['checks'][name]
            assert source['passed'] is True
            assert source.get('dimension',check['dimension'])==check['dimension']
            assert source.get('legacy_spelling_supported') is not False
            assert source.get('evidence_kind')!='migration-and-rejection'
            key='component:'+kind+':'+name+':'+check['dimension']
            leaf=dict(passed=True,dimension=check['dimension'],contracts=[],
                oracle=source.get('oracle') or 'Independently verified native component result and retained artifacts.',
                source_check=dependency,
                source_row_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest())
            assert key not in checks or checks[key]==leaf
            checks[key]=leaf;linked.append(key)
        if linked:check['dependencies']=linked
    return checks


def merge_review_inputs(inputs, reports):
    for report in reports:
        for group in ('source_inputs', 'inputs'):
            for name, digest in report.get(group, {}).items():
                assert name not in inputs or inputs[name] == digest, name
                inputs[name] = digest
    return inputs
