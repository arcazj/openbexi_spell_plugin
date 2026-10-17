"""Independently review and promote the final 190 v0.5 language requirements.

The previously published 573 requirements must first be refreshed with
record_language_regressions.py. This records language acceptance only; release
publication additionally requires the complete test and artifact gates.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'distribution'),
               str(ROOT/'source_port'), str(ROOT/'driver_plugin/src')]
from aggregate_support import complete_sequence, read, ref, sha
from check import validate


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


def qualify(sequence_path, native_wheel, driver_wheel, native_pair, refreshed_path):
    from limit_full_report import qualify as limits
    from data_aggregate_report import qualify as data
    from database_complete_report import qualify as database
    from special_complete_report import qualify as special
    from observation_complete_report import qualify as observation
    from command_complete_report import qualify as command
    from flow_complete_report import qualify as flow
    from ui_complete_report import qualify as ui
    from common_complete_report import qualify as common

    sequence, paths, _, _ = complete_sequence(sequence_path, ('limit', 'limit-features'))
    image = sequence['image']
    inventory, coverage = read(ROOT/'conformance/inventory.json'), read(ROOT/'conformance/coverage.json')
    before = validate(inventory, coverage, ROOT)
    assert before['counts'] == {'QUALIFIED': 573, 'OPEN': 190} and not before['accepted']
    refreshed = read(refreshed_path)
    assert refreshed['passed'] and refreshed['runtime_image'] == image
    assert refreshed['counts'] == before['counts']
    assert refreshed['coverage_sha256'] == sha(ROOT/'conformance/coverage.json')
    for row in coverage['rows']:
        if row['status'] == 'QUALIFIED':
            for binding in row['evidence'].values():
                assert read(ROOT/binding['report'])['runtime_image'] == image

    args = (sequence_path, native_wheel, driver_wheel)
    reviewers = (
        ('limit', 52, lambda: limits(paths['limit-features'], paths['limit'], sequence_path,
                                    sequence['source_commit'], image, native_wheel, driver_wheel)),
        ('data', 6, lambda: data(sequence_path)),
        ('database', 12, lambda: database(*args)),
        ('special', 45, lambda: special(*args)),
        ('observation', 16, lambda: observation(*args)),
        ('command', 19, lambda: command(*args)),
        ('flow', 15, lambda: flow(*args)),
        ('ui', 8, lambda: ui(*args, native_pair)),
        ('common', 17, lambda: common(*args, native_pair)),
    )
    selected, reports = {}, {}
    for family, count, reviewer in reviewers:
        print('Reviewing '+family, flush=True)
        report = reviewer()
        assert report['passed'] and report['runtime_image'] == image
        contracts = report['qualified_contracts']
        assert len(contracts) == len(set(contracts)) == count
        assert not set(contracts) & selected.keys()
        assert all(row['passed'] is True for row in report['checks'].values())
        name = 'conformance/evidence/v05_'+family+'_complete.json'
        write(ROOT/name, report)
        reports[family] = dict(ref(ROOT/name), qualified_contracts=count)
        selected.update({identifier: name for identifier in contracts})
        print(f'{family}: {count} requirements independently reviewed', flush=True)
    assert set(selected) == {row['id'] for row in coverage['rows'] if row['status'] == 'OPEN'}
    promoted = deepcopy(coverage)
    for row in promoted['rows']:
        if row['id'] not in selected:
            continue
        name = selected[row['id']]
        row.update(status='QUALIFIED', evidence={dimension: dict(report=name,
            sha256=sha(ROOT/name), check=row['id']+':'+dimension)
            for dimension in ('positive', 'boundary', 'failure', 'recovery')})
        row.pop('remaining', None)
    gate = validate(inventory, promoted, ROOT)
    assert gate['accepted'] and gate['total'] == 763 and gate['counts'].get('QUALIFIED') == 763
    assert gate['counts'].get('OPEN', 0) == 0
    previous = sha(ROOT/'conformance/coverage.json')
    write(ROOT/'conformance/coverage.json', promoted)
    result = dict(passed=True, scope='All original 763 language requirements; publication gates remain separate',
        runtime_image=image, source_commit=sequence['source_commit'], sequence=ref(sequence_path),
        prior_refresh=ref(refreshed_path), native_pair=ref(native_pair),
        native_wheel=ref(native_wheel), driver_wheel=ref(driver_wheel),
        before_counts=before['counts'], before_coverage_sha256=previous,
        counts=gate['counts'], total=763, coverage_sha256=sha(ROOT/'conformance/coverage.json'),
        newly_qualified=sorted(selected), reports=reports, full_v05_language_accepted=True,
        full_v05_release_accepted=False, full_v06_accepted=False)
    write(ROOT/'distribution/evidence/v05-language-promotions.json', result)
    print(json.dumps(dict(passed=True, counts=gate['counts'], total=763)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sequence', 'native-wheel', 'driver-wheel', 'native-pair', 'refreshed'):
        parser.add_argument('--'+name, type=Path, required=True)
    options = parser.parse_args()
    qualify(options.sequence.resolve(), options.native_wheel.resolve(), options.driver_wheel.resolve(),
            options.native_pair.resolve(), options.refreshed.resolve())
