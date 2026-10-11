"""Use the original Python 3 library manifests, not Python 2-only sources.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import re


def libraries(source):
    result = {}
    for manifest in sorted((source / 'lib').glob('SPELL_*/Makefile.am')):
        logical = manifest.read_text().replace('\\\n', ' ')
        name = manifest.parent.name
        assignments = re.findall(r'^lib' + name + r'_v3_la_SOURCES\s*=\s*([^\n]+)', logical, re.M)
        if len(assignments) != 1:
            raise ValueError('Ambiguous Python 3 source manifest: ' + name)
        units = []
        for entry in assignments[0].split():
            path = (manifest.parent / entry).resolve()
            if not path.is_relative_to(manifest.parent.resolve()) or path.suffix != '.C' or not path.is_file():
                raise ValueError('Unexpected original source entry: ' + entry)
            units.append(path)
        if len(units) != len(set(units)):
            raise ValueError('Duplicate source entry: ' + name)
        excluded = sorted(set(manifest.parent.rglob('*.C')) - set(units))
        result[name] = {'manifest':manifest.relative_to(source).as_posix(),
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'units':[p.relative_to(source).as_posix() for p in units],
            'not_in_python3_manifest':[p.relative_to(source).as_posix() for p in excluded]}
    if not result:
        raise ValueError('Original library manifests not found')
    return result
