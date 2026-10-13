"""LRM p.68 Notify callable preserving the original Notify modifier.

SPDX-License-Identifier: LGPL-3.0-or-later
Notify remains a string-compatible dictionary key. Its callable spelling
delegates to the unchanged original Notification helper. Exact built-in str
identity is intentionally replaced by this narrow callable string subtype.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ARCHIVE_SHA256 = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
PREIMAGES = {
    'spell/lang/modifiers.py': '799c35daa6af10f8755decb6a5e12a366547ac38ef99138898b294ff4421d8df',
    'spell/utils/grpc_utils.py': 'bb748250b475adb305286dbda0603da886b894b4ac105bf010310a8302004ef7',
    'spell/lib/adapter/config.py': 'ba5ca0c1183e994dee015b0d617e31dc316827b58ca1614525a523e1e0211dc6',
}
ORIGINALS = dict(PREIMAGES, **{
    'spell/utils/grpc_utils.py': 'aa6c7f35a2159c4dbd8d98422be7a606b7061d3aba043c738900c1eab19e7049',
})


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_once(raw, old, new):
    old, new = old.encode(), new.encode()
    if raw.count(old) != 1:
        raise ValueError('Unexpected replacement occurrence count')
    return raw.replace(old, new)


def apply(name, raw):
    if digest(raw) != PREIMAGES[name]:
        raise ValueError('Unexpected notification preimage: ' + name)
    if name == 'spell/lang/modifiers.py':
        raw = replace_once(raw, "Notify = 'Notify'", '''def _restore_notify_modifier():
    return Notify


class _NotifyModifier(str):
    """The Notify modifier is also the LRM notification callable.

    Lazy import avoids the original functions -> modifiers import cycle.
    String equality and hashing preserve keyword/config dictionary lookups.
    """
    def __new__(cls, value='Notify'):
        if value != 'Notify':
            raise ValueError('The Notify modifier has fixed text')
        return str.__new__(cls, 'Notify')

    def __copy__(self):
        return Notify

    def __deepcopy__(self, memo):
        return Notify

    def __reduce__(self):
        return (_restore_notify_modifier, ())

    def __call__(self, *args, **kwargs):
        from spell.lang.functions import Notification
        return Notification(*args, **kwargs)


Notify = _NotifyModifier('Notify')''')
    elif name == 'spell/utils/grpc_utils.py':
        raw = replace_once(raw, 'from spell.lib.adapter.utctime import TIME, NOW',
            'from spell.lib.adapter.utctime import TIME, NOW\nfrom spell.lang.modifiers import Notify as _notify_modifier')
        raw = replace_once(raw, '\nPACK_MSG_MAP = {', '''
PACK_MSG_MAP = {
        # Preserve the original modifier's wire string representation.
        type(_notify_modifier): lambda value: grpc_wrappers.StringValue(value=str(value)),''')
    elif name == 'spell/lib/adapter/config.py':
        raw = replace_once(raw, 'from spell.lib.exception import SyntaxException',
            'from spell.lib.exception import SyntaxException\nfrom spell.lang.modifiers import Notify as _notify_modifier')
        raw = replace_once(raw, 'if type(object)!=str:',
            'if type(object)!=str and object is not _notify_modifier:')
    compile(raw, name, 'exec')
    return raw


def apply_tree(site, archive, output):
    site, archive, output = Path(site), Path(archive), Path(output)
    if digest(archive.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError('Unexpected original SPELL archive')
    with zipfile.ZipFile(archive) as bundle:
        original = {name: bundle.read('src/spell/' + name) for name in PREIMAGES}
    ported = {name: (site/name).read_bytes() for name in PREIMAGES}
    patched = {}
    for name in PREIMAGES:
        if digest(original[name]) != ORIGINALS[name]:
            raise ValueError('Unexpected original notification source: ' + name)
        patched[name] = apply(name, ported[name])
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    for name in PREIMAGES:
        sources[name] = {}
        for label, contents in (('original', original), ('ported', ported), ('patched', patched)):
            target = output/label/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents[name])
            sources[name][label + '_sha256'] = digest(contents[name])
        (site/name).write_bytes(patched[name])
    recipe = Path(__file__).read_bytes()
    (output/Path(__file__).name).write_bytes(recipe)
    report = dict(schema='openbexi.spell.notification-overlay/1', archive_sha256=ARCHIVE_SHA256,
        recipe_sha256=digest(recipe), sources=sources,
        limitation='Diagnostic overlay; installed RECORD is superseded for these three files. A fresh composed wheel is required for distribution acceptance.')
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return report
