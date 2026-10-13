"""Compose the qualified original-source corrections before compilation/packaging.

SPDX-License-Identifier: GPL-3.0-or-later
The central CPython port remains byte-for-byte unchanged. Each subsequent recipe
checks its complete original/ported preimage; manifests preserve the whole chain.
"""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

import cmd_patches
import data_files_native_patches
import data_files_patches
import dta_native_patches
import dta_time_patches
import flow_patches
import obs_patches
import ui_native_patches

ARCHIVE_SHA256 = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
RECIPE_NAMES = (
    'integrated_patches.py', 'native_patches.py', 'patches.py',
    'data_files_native_patches.py', 'data_files_patches.py',
    'dta_native_patches.py', 'dta_time_patches.py',
    'flow_patches.py', 'flow_analyze.py', 'obs_patches.py', 'ui_native_patches.py',
    'cmd_patches.py',
)
IDENTITY_HEADER = 'include/SPELL_WS/SPELLcontinuationSource.H'
NATIVE_NAMES = tuple(sorted((data_files_native_patches.NAME, dta_native_patches.SOURCE,
                            ui_native_patches.SOURCE, *dta_time_patches.PREIMAGES,
                            *flow_patches.PREIMAGES)))
PYTHON_NAMES = tuple(sorted((*data_files_patches.PREIMAGES, *obs_patches.PREIMAGES, *cmd_patches.PREIMAGES,
                            'spell/lang/helpers/exechelper.py')))


def digest(content):
    return hashlib.sha256(content).hexdigest()


def recipe_hashes(directory=None):
    directory = Path(directory) if directory else Path(__file__).parent
    return {name: {'sha256': digest((directory/name).read_bytes()),
                   'lf_sha256': digest((directory/name).read_bytes().replace(b'\r\n', b'\n'))}
            for name in RECIPE_NAMES}


def checkpoint_identity(base, recipes):
    # The original port fingerprint covers its native bodies and central recipe.
    # Also bind all composed native/Python corrections, including this dispatcher.
    identity = {'profile': 'original-spell-integrated/1', 'central_identity': base,
                'recipes': {name: row['lf_sha256'] for name, row in recipes.items()}}
    return digest(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode())


def archive_sources(archive, names):
    archive = Path(archive)
    if digest(archive.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError('Unexpected original SPELL source archive')
    with zipfile.ZipFile(archive) as bundle:
        return {name: bundle.read(name) for name in names}


def write_evidence(output, original, ported, patched, recipes):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    for name in sorted(patched):
        records[name] = {}
        for label, contents in (('original', original), ('ported', ported), ('patched', patched)):
            if name not in contents:
                continue
            target = output/label/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents[name])
            records[name][label + '_sha256'] = digest(contents[name])
    for name in recipes:
        target = output/'recipes'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(__file__).with_name(name).read_bytes())
    return records


def apply_native_tree(source, archive, output):
    source = Path(source)
    original = archive_sources(archive, NATIVE_NAMES)
    ported = {name: (source/name).read_bytes() for name in NATIVE_NAMES}
    patched = {}
    for name in NATIVE_NAMES:
        if name == data_files_native_patches.NAME:
            patched[name] = data_files_native_patches.apply(original[name], ported[name])
        elif name == dta_native_patches.SOURCE:
            patched[name] = dta_native_patches.apply(name, original[name], ported[name])
        elif name == ui_native_patches.SOURCE:
            patched[name] = ui_native_patches.apply(name, original[name], ported[name])
        elif name in dta_time_patches.PREIMAGES:
            patched[name] = dta_time_patches.apply(name, original[name], ported[name])
    # Existing tree recipes run in a scratch tree. Validate every preimage before
    # changing the actual build tree, so a rejected input leaves it untouched.
    with tempfile.TemporaryDirectory(prefix='spell-native-composition-') as folder:
        scratch = Path(folder)
        for name in flow_patches.PREIMAGES:
            target = scratch/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(ported[name])
        flow_patches.apply_tree(scratch)
        patched.update({name: (scratch/name).read_bytes() for name in flow_patches.PREIMAGES})
    recipes = recipe_hashes()
    header = (source/IDENTITY_HEADER).read_bytes()
    pattern = rb'(static const char continuationSourceIdentity\[\] = ")([0-9a-f]{64})(";)'
    matches = list(re.finditer(pattern, header))
    if len(matches) != 1:
        raise ValueError('Unexpected central continuation identity header')
    base = matches[0].group(2).decode()
    identity = checkpoint_identity(base, recipes)
    ported[IDENTITY_HEADER] = header
    patched[IDENTITY_HEADER] = re.sub(pattern, lambda match: match.group(1) + identity.encode() + match.group(3), header)
    records = write_evidence(output, original, ported, patched, recipes)
    for name, content in patched.items():
        (source/name).write_bytes(content)
    report = {'schema': 'openbexi.spell.integrated-native/1', 'archive_sha256': ARCHIVE_SHA256,
              'recipes': recipes, 'sources': records,
              'checkpoint': {'central_identity': base, 'integrated_identity': identity}}
    (Path(output)/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return report


def apply_python_tree(site, archive, output):
    site = Path(site)
    originals = archive_sources(archive, ['src/spell/' + name for name in PYTHON_NAMES])
    original = {name: originals['src/spell/' + name] for name in PYTHON_NAMES}
    ported = {name: (site/name).read_bytes() for name in PYTHON_NAMES}
    with tempfile.TemporaryDirectory(prefix='spell-python-composition-') as folder:
        scratch = Path(folder)/'site'
        for name, content in ported.items():
            target = scratch/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for name in data_files_patches.PREIMAGES:
            (scratch/name).write_bytes(data_files_patches.apply(name, ported[name]))
        flow_patches.apply_python_tree(scratch)
        obs_patches.apply_tree(scratch, Path(folder)/'obs')
        cmd_patches.apply_tree(scratch, Path(folder)/'cmd')
        patched = {name: (scratch/name).read_bytes() for name in PYTHON_NAMES}
        for name, content in patched.items():
            compile(content, name, 'exec')
    recipes = recipe_hashes()
    records = write_evidence(output, original, ported, patched, recipes)
    for name, content in patched.items():
        (site/name).write_bytes(content)
    report = {'schema': 'openbexi.spell.integrated-python/1', 'archive_sha256': ARCHIVE_SHA256,
              'recipes': recipes, 'sources': records}
    (Path(output)/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return report
