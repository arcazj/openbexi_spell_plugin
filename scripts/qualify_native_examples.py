"""Run the IDE's explicit-import example through the original native executor."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import qualify_host_adapter as host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', default='openbexi-spell-host:0.3.0')
    args = parser.parse_args()
    output = args.output.resolve() / uuid.uuid4().hex
    project = output / 'project'
    project.mkdir(parents=True)
    source = args.examples.resolve() / 'test_spell.py'
    shutil.copyfile(source, project / source.name)
    host.IMAGE, host.EVIDENCE = args.image, output
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    report = {'passed': False, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'image': image, 'checks': []}
    client = host.Client(project)
    try:
        client.launch(source.name, noDebug=True)
        client.request('configurationDone')
        assert client.event('exited')['exitCode'] == 0, 'Native example failed; inspect transcript'
        client.event('terminated')
        actual = json.loads(client.read_file('test_spell_result.json'))
        assert actual['answer'] == 42 and actual['native_data'] and actual['shared_data_cleaned']
        assert '/site-packages/spell/lib/' in actual['original_library']
        assert any(m.get('event') == 'output' and 'SPELL_EXAMPLE_PASS' in m['body']['output']
                   for m in client.transcript)
        assert (project / source.name).read_bytes() == source.read_bytes()
        report.update(passed=True, checks=['original library explicit import', 'native DataContainer and Var',
            'relative and absolute TIME arithmetic', 'native Step transitions',
            'original shared data round trip and cleanup', 'result file and terminal output',
            'source snapshot unchanged'])
    finally:
        client.close('native-example')
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'evidence': str(output), **report}, indent=2))


if __name__ == '__main__':
    main()
