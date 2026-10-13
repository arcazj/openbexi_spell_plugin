"""Freeze only the documented Notify function and Example109 native scope."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from check import DIMENSIONS, supported_check

ROOT = Path(__file__).resolve().parents[1]
IDS = ['CMP-LRM244-FUNCTION-NOTIFY', 'CMP-LRM244-EXAMPLE-109']
ORACLE = ('LRM p.68: the exact Notify(name,value,status) spelling emits one original native ITEM per call '
          'for SUCCESS/IN PROGRESS/FAILED and returns None; empty and UTF-8 values survive; malformed arity '
          'raises original SyntaxException without ITEM effects; a later valid call succeeds. Existing Notify '
          'modifier configuration, serialization and actual executor checkpoint recovery remain operational.')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    raw = args.result.read_bytes()
    report = json.loads(raw)
    assert not report.get('infrastructure_error')
    assert all(row['passed'] for row in report['checks'].values())
    for name, expected in report['inputs'].items():
        assert digest((ROOT/name).read_bytes()) == expected, name
    assert report['runtime_sources']['overlay'] is not None
    baseline_raw = args.baseline.read_bytes()
    baseline = json.loads(baseline_raw)
    assert all(not baseline['checks']['notify:'+dimension]['passed'] for dimension in DIMENSIONS)
    source_checks = copy.deepcopy(report['checks'])
    for identifier, row in report['checks'].items():
        row['contracts'] = []
        row.setdefault('oracle', 'Independent native compatibility/regression oracle; no new clause allocation.')
    compatibility = [name for name in source_checks if name.startswith(('modifier:', 'legacy:'))]
    for dimension in DIMENSIONS:
        parent = report['checks']['notify:'+dimension]
        parent.update(contracts=IDS, oracle=ORACLE, legacy_spelling_supported=True, dependencies=[])
        for name in compatibility:
            leaf = copy.deepcopy(report['checks'][name])
            leaf.update(dimension=dimension, source_scenario=name,
                source_dimension=source_checks[name]['dimension'],
                source_row_sha256=digest(json.dumps(source_checks[name],sort_keys=True).encode()))
            key = 'compatibility:' + dimension + ':' + name
            report['checks'][key] = leaf
            parent['dependencies'].append(key)
        assert supported_check(report, 'notify:'+dimension, dimension)
    report['inputs']['conformance/notification_report.py'] = digest(Path(__file__).read_bytes())
    report.update(schema='openbexi.spell.notification-checkpoint/1', qualified_ids=IDS,
        full_v05_accepted=False, full_v06_accepted=False,
        source_conflict={
            'manual':'LRM2.4.4 p68 Example109 spells Notify; original2.6.10 exports callable Notification and string modifier Notify.',
            'resolution':'One fixed-text callable str subtype token, shared by modifiers/functions/runtime imports, delegates unchanged Notification. Copy/deepcopy/pickle reconstruct the singleton. Exact built-in str identity is intentionally no longer true.',
            'preserved':'String equality/hash/repr, keyword and dictionary config, exact config validation, original protobuf string representation, old Notification, and real native ON_LINE/ON_STEP checkpoint recovery.',
            'limitations':['No installed desktop/tabular rendering claim.','No new Prompt timeout/default or cross-family Notify modifier clause claim.',
                'No arbitrary string-subclass compatibility claim.','Diagnostic overlay supersedes three installed RECORD entries; fresh composed wheels remain required.']},
        raw_result={'path':str(args.result.resolve()),'sha256':digest(raw)},
        baseline={'path':str(args.baseline.resolve()),'sha256':digest(baseline_raw),
                  'runtime_image':baseline['runtime_image'],
                  'checks':baseline['checks'],
                  'interpretation':'Four exact documented calls fail TypeError because Notify is a plain string. Baseline checkpoint attempts also fail the new callable-token assertions; their timeouts are retained, not presented as an independent old checkpoint defect.'})
    output = ROOT/'conformance/evidence/notification.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(report=str(output),sha256=digest(output.read_bytes()),qualified_ids=IDS,
        native_checks=len(source_checks),full_v05_accepted=False,full_v06_accepted=False),indent=2))


if __name__ == '__main__':
    main()
