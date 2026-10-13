"""Reject release acceptance unless every original inventory row has evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def supported_check(report, identifier, dimension, visiting=None):
    """A passing migration test cannot stand in for supported language behavior."""
    visiting = set() if visiting is None else visiting
    if identifier in visiting:
        raise ValueError('Cyclic evidence dependency: ' + identifier)
    check = report['checks'].get(identifier)
    if (not check or check.get('passed') is not True or check.get('dimension') != dimension
            or not check.get('oracle') or check.get('legacy_spelling_supported') is False
            or check.get('evidence_kind') == 'migration-and-rejection'):
        return False
    visiting.add(identifier)
    try:
        return all(supported_check(report, child, dimension, visiting)
                   for child in check.get('dependencies', []))
    finally:
        visiting.remove(identifier)


def validate(inventory, coverage, root):
    # Reports and large source archives recur across hundreds of dimensions.
    # Caches belong to this validation only; subsequent validations rehash files.
    digests, reports = {}, {}
    def digest(path):
        path = path.resolve()
        if path not in digests:
            digests[path] = sha(path)
        return digests[path]

    rows = inventory['rows']
    ids = [row['id'] for row in rows]
    if len(ids) != 763 or len(set(ids)) != 763:
        raise ValueError('The original inventory must retain 763 unique rows')
    allocations = coverage['rows']
    if len(allocations) != 763 or {row['id'] for row in allocations} != set(ids):
        raise ValueError('Coverage must allocate every original row exactly once')
    if coverage['inventory_sha256'] != digest(root / 'conformance/inventory.json'):
        raise ValueError('Inventory changed after coverage allocation')
    failures = []
    counts = Counter()
    for row in allocations:
        counts[row['status']] += 1
        if row['status'] != 'QUALIFIED':
            failures.append({'id': row['id'], 'reason': row.get('remaining', 'Contract remains open')})
            continue
        if set(row['evidence']) != set(DIMENSIONS):
            raise ValueError('Missing independent evidence dimension: ' + row['id'])
        for dimension in DIMENSIONS:
            item = row['evidence'][dimension]
            path = (root / item['report']).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError('Missing or external evidence report: ' + row['id'])
            if digest(path) != item['sha256']:
                raise ValueError('Evidence report hash mismatch: ' + row['id'])
            if path not in reports:
                reports[path] = json.loads(path.read_text(encoding='utf-8'))
            report = reports[path]
            check = report['checks'][item['check']]
            if (not supported_check(report, item['check'], dimension)
                    or row['id'] not in check.get('contracts', [])):
                raise ValueError('Report does not qualify this contract/dimension: ' + row['id'])
            if not report.get('runtime_image') or not report.get('inputs'):
                raise ValueError('Report lacks runtime and source identities: ' + row['id'])
            for name, expected_digest in report['inputs'].items():
                source = (root / name).resolve()
                if not source.is_relative_to(root.resolve()) or not source.is_file() or digest(source) != expected_digest:
                    raise ValueError('Evidence input changed: ' + name)
    return {'release': 'v0.5', 'accepted': not failures, 'total': 763,
            'counts': dict(counts), 'open_rows': failures,
            'v0.6_dependency_satisfied': not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / 'conformance/inventory.json').read_text(encoding='utf-8'))
    coverage = json.loads((root / 'conformance/coverage.json').read_text(encoding='utf-8'))
    result = validate(inventory, coverage, root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'open_rows'}))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
