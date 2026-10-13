"""Compile explicit changed native units and relink their original dependency graphs.

Use inside a derived diagnostic build image after checked-preimage patches have
been applied to /source. /out is read-only to this helper. Output binaries require
new behavior qualification; compilation does not promote any release.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import sysconfig


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(changed, output, source=Path('/source'), baseline=Path('/out')):
    output.mkdir(parents=True, exist_ok=False)
    reports = {name: json.loads((baseline / (name + '-build.json')).read_text())
               for name in ('native', 'executor', 'context')}
    native, executor, context = (reports[name] for name in ('native', 'executor', 'context'))
    library_units = {row['unit']: row for row in executor['units']}
    known = dict(library_units)
    for program in context['programs'].values():
        known.update({row['unit']: row for row in program['units']})
    changed = sorted(set(changed))
    if not changed or any(name not in known for name in changed):
        raise ValueError('Changed-unit list must name original native manifest units')
    result = {'passed': False, 'full_qualification_passed': False,
              'recipe_sha256': sha(Path(__file__)),
              'baseline_reports': {name: sha(baseline / (name + '-build.json')) for name in reports},
              'compiler': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
              'units': {}, 'artifacts': {}}
    objects = {}

    def run(command, name):
        completed = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
        log = output / (name + '.log')
        log.write_text(completed.stdout + completed.stderr)
        record = {'command': list(map(str, command)), 'exit_code': completed.returncode,
                  'log_sha256': sha(log)}
        if completed.returncode:
            result['failed_operation'] = record
            raise RuntimeError('Native compile/link failed: ' + name)
        return record

    try:
        for name in changed:
            path = (source / name).resolve(strict=True)
            if not path.is_relative_to(source.resolve()) or sha(path) == known[name]['sha256']:
                raise ValueError('Changed unit escaped source tree or is unchanged: ' + name)
            obj = output / known[name]['object']
            row = run([*native['flags'], '-c', path, '-o', obj], name.replace('/', '_'))
            row.update(original_sha256=known[name]['sha256'], patched_sha256=sha(path),
                       object=obj.name, object_sha256=sha(obj))
            result['units'][name] = row
            objects[name] = obj

        def selected(row):
            return objects.get(row['unit'], baseline / row['object'])

        common = ['-L' + sysconfig.get_config_var('LIBDIR'), '-lpython3.13',
                  '-llog4cplus', '-lxerces-c', '-lz', '-lmenu', '-lncurses']

        def linked(name, command):
            artifact = output / name
            row = run([*command, '-o', artifact], name + '-link')
            row.update(sha256=sha(artifact), original_sha256=sha(baseline / name))
            result['artifacts'][name] = row

        if set(changed) & library_units.keys():
            extras = {row['unit']: row for field in ('units', 'analysis_units', 'dta_units')
                      for row in native[field]}
            rows = executor['units'] + [extras[name] for name in ('ws_filter.cpp', 'continuation.cpp')]
            linked('libspell_executor313.so', ['c++', '-shared', '-pthread',
                   '-fsanitize=address,undefined', '-Wl,--no-undefined',
                   *map(selected, rows), *common])
        for name, program in context['programs'].items():
            # These executables bind the shared singleton runtime via $ORIGIN;
            # their unchanged main programs need no relink after a library fix.
            if 'shared_runtime' in program:
                mains = [row for row in program['units'] if row['unit'].startswith('src/')]
                if set(changed) & {row['unit'] for row in mains}:
                    library = output if (output / 'libspell_executor313.so').exists() else baseline
                    linked(program['executable'], ['c++', '-pthread', '-fsanitize=address,undefined',
                        *map(selected, mains), '-L' + str(library), '-lspell_executor313',
                        '-Wl,-rpath,$ORIGIN', '-L' + sysconfig.get_config_var('LIBDIR'), '-lpython3.13'])
            elif set(changed) & {row['unit'] for row in program['units']}:
                linked(program['executable'], ['c++', '-pthread', '-fsanitize=address,undefined',
                       '-Wl,--no-undefined', *map(selected, program['units']), *common])
        if not result['artifacts']:
            raise ValueError('Changed units produced no executable or shared-library artifact')
        result['passed'] = True
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        (output / 'incremental-build.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--changed', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild(args.changed, args.output), indent=2))
