"""Keep volatile test-run evidence beside, rather than inside, a native wheel.

SPDX-License-Identifier: GPL-3.0-or-later
The unchanged native recorder has already checked every native gate. This step
changes only provenance packaging; it never removes or edits executable content.
The full, per-run report remains an exported distribution sidecar.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stabilize(package, output):
    output.mkdir(parents=True, exist_ok=False)
    wheel, = (package / 'wheels').glob('*.whl')
    with zipfile.ZipFile(wheel) as archive:
        entries = {item.filename: (item, archive.read(item)) for item in archive.infolist()}
    report_name = 'spell_native/provenance/NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json'
    original_report = json.loads(entries.pop(report_name)[1])
    manifest_name = 'spell_native/manifest.json'
    info, data = entries[manifest_name]
    manifest = json.loads(data)
    # Native gate outputs contain independently useful diagnostics with process
    # IDs, elapsed times, and addresses. Those are not package build inputs.
    manifest.pop('qualification_sha256')
    stable = {
        'policy': 'source_port/record_native.py --service-recovery-policy',
        'recorder_sha256': manifest['inputs']['record_native.py'],
        'archive_sha256': manifest['archive_sha256'],
        'native_artifacts': manifest['native_artifacts'],
        'evidence_location': 'External per-build native-qualification.json sidecar',
        'full_v05_conformance_accepted': False,
        'v06_distribution_accepted': False,
    }
    stable_data = (json.dumps(stable, indent=2, sort_keys=True) + '\n').encode()
    manifest['native_gate_policy_sha256'] = digest(stable_data)
    entries[manifest_name] = (info, (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    stable_name = 'spell_native/provenance/NATIVE_GATE_POLICY.json'
    entries[stable_name] = (zipfile.ZipInfo(stable_name), stable_data)
    # Include the complete extra packaging recipe with corresponding source.
    for path in sorted(Path(__file__).parent.glob('*')):
        if path.is_file():
            name = 'spell_native/provenance/distribution/' + path.name
            entries[name] = (zipfile.ZipInfo(name), path.read_bytes())
    record_name, = [name for name in entries if name.endswith('.dist-info/RECORD')]
    entries.pop(record_name)
    record = io.StringIO(newline='')
    writer = csv.writer(record, lineterminator='\n')
    for name, (_, content) in sorted(entries.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
        writer.writerow((name, 'sha256=' + encoded, len(content)))
    writer.writerow((record_name, '', ''))
    entries[record_name] = (zipfile.ZipInfo(record_name), record.getvalue().encode())
    target = output / 'wheels' / wheel.name
    target.parent.mkdir()
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, (original, content) in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = original.external_attr or (0o100644 << 16)
            archive.writestr(info, content)
    result = {
        'wheel': target.name, 'sha256': digest(target.read_bytes()),
        'native_artifacts': manifest['native_artifacts'],
        'python_sources': manifest['python_sources'],
        'composition': manifest.get('composition'),
        'native_gate_policy': stable,
        'volatile_evidence_separated': True,
        'native_runtime_tests': original_report['executor_runtime']['tests'],
        'context_lifecycle_tests': original_report['context_runtime']['tests'],
        'native_content_unchanged': all(entries['spell_native/bin/' + name][1] ==
                                       (package / 'src/spell_native/bin' / name).read_bytes()
                                       for name in manifest['native_artifacts']),
    }
    assert result['native_content_unchanged']
    (output / 'package-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stabilize(args.package, args.output), indent=2))
