"""Verify/export native milestone evidence. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    evidence = args.evidence.resolve()
    build = json.loads((evidence/'native-build.json').read_text())
    runtime = json.loads((evidence/'util-runtime.json').read_text())
    required = ('link_exit_code','runtime_exit_code','embed_build_exit_code','embed_runtime_exit_code')
    if any(build.get(key) != 0 for key in required) or any(u['exit_code'] for u in build['units']):
        raise ValueError('Native build/link/runtime qualification failed')
    if any(runtime[key] for key in ('failures','errors','skips')) or runtime['tests'] < 16:
        raise ValueError('Native behavior qualification is incomplete')
    if build['embedding'] != {'owned_interpreter_cycles':3,'foreign_thread_finalize_rejected':True}:
        raise ValueError('Interpreter ownership qualification is incomplete')
    for name, expected in build['input_sources'].items():
        path = root/'source_port'/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Build evidence predates source: '+name)
    artifacts = {}
    for path in sorted(evidence.iterdir()):
        if path.is_file():
            artifacts[path.name] = {'bytes':path.stat().st_size,
                                   'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    report = {
        'milestone':'CPython 3.13 native UTIL compiler/frame/error ownership',
        'release':'v0.2 remains open', 'full_spell_native_qualified':False,
        'qualification_scope':'Linux x86_64, GIL-enabled CPython 3.13; original UTIL/SYN linked in a test extension and embedding executable',
        'patches':json.loads((evidence/'native-patches.json').read_text()),
        'build':build, 'runtime':runtime, 'artifacts':artifacts,
        'gaps':['DTA runtime and memory qualification','EXC Step/Goto/procedure control integration',
                'WS frame serialization/recovery','complete native/context/service setup and cleanup',
                'reproducible production native packaging','Windows native qualification'],
        'source_alpha_evidence':'source-v0.2.0a1 remains the separate historical Python/RPC wheel milestone',
    }
    destination = root/'docs/NATIVE_UTIL_QUALIFICATION.json'
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tests':runtime['tests'], 'embedding_cycles':3,
        'downstream_syntax_pass':sum(u['exit_code']==0 for u in build['downstream_syntax']),
        'downstream_syntax_fail':sum(u['exit_code']!=0 for u in build['downstream_syntax']),
        'report':str(destination)}))


if __name__ == '__main__':
    main()
