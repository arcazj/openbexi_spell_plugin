"""Exact-source LRM 2.4.4 display/workspace compatibility corrections.

SPDX-License-Identifier: GPL-3.0-or-later
The original TASK protobuf schema is retained. Workspace calls use a private
driver discriminator over its existing Display configuration dictionary.
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lang/functions.py': '168836e0a4bc96f8e2a67b5190f532b2154d6be1d697f1f818341349c221e735',
    'spell/lang/constants.py': '6a3a6e80e712bfcca6bc1bbb2d6f50b7b444b63d8396b9e0c9884c2fbc1dbb63',
    'spell/lang/modifiers.py': 'd35442e9de8e967aca334566cf009ff559a0bda1a040154d3b9c661fa4665452',
    'spell/lang/helpers/tskhelper.py': 'e45cd0f5a1c69706b0739878a9a993346979cd11013215e56bee87837531b58f',
    'spell/lib/adapter/task.py': '924d5e4722e0bc58228256717067e0e9f5efa812cf7be14e9807808a83f6f8fe',
    'openbexi_dss_proxy/task.py': 'abe7a3a954b671a117775ea57c2ef013b7733192746a90fa7ce6f7591d98288e',
    'openbexi_spell_dss/ground.py': 'cb7524ea79718eec5c8467b701d00fe15318781cb7b5509df8fccfc3eb9aea07',
    'openbexi_spell_dss/rpc.py': '3fd63bd7b16fa3f2cad0d8f2dd1d9071a1890f69cb266f1e1e6172932565cd52',
    'openbexi_spell_dss/journal.py': '2d5df422f838235793cd5d21c41eb374cf7c8514fd747ded98d794cf763287f3',
}


def replace(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Display patch anchor differs')
    return source.replace(before, after)


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Unexpected display source preimage: ' + name)
    source = raw.decode('utf-8')
    if name == 'spell/lang/constants.py':
        source += "\n# LRM 2.4.4 section 4.13.2, display output formats.\nPS = 'PS'\nVECTOR = 'VECTOR'\n"
    elif name == 'spell/lang/modifiers.py':
        source += "\n# LRM 2.4.4 section 4.13.1, driver-dependent display routing.\nMonitor = 'Monitor'\nReuse = 'Reuse'\n"
    elif name == 'spell/lang/functions.py':
        for action in ('Open', 'Close'):
            source += '''

def %sWorkspace(*args, **kargs):
    """%s a named group of GCS displays (LRM 2.4.4 section 4.13)."""
    from .helpers.tskhelper import %sWorkspace_Helper
    helper = %sWorkspace_Helper()
    helper.configure(*args, **kargs)
    return helper.execute(*args, **kargs)
''' % (action, action, action, action)
    elif name == 'spell/lang/helpers/tskhelper.py':
        for action, following in (('Open', 'CloseDisplay'), ('Close', 'StartProc')):
            start = source.index('class ' + action + 'Display_Helper(')
            end = source.index('class ' + following + '_Helper(', start)
            section = source[start:end]
            section = section.replace(action + 'Display', action + 'Workspace')
            section = section.replace(action.lower() + 'Display', action.lower() + 'Workspace')
            section = section.replace('display', 'workspace').replace('Display', 'Workspace')
            source += '\n' + section
    elif name == 'spell/lib/adapter/task.py':
        for action in ('open', 'close'):
            source += '''

    def %sWorkspace(self, *args, **kargs):
        if len(args) < 1:
            raise SyntaxException("Expected a workspace name")
        useConfig = self.buildConfig(args, kargs, self.getConfig(), INTERFACE_DEFAULTS)
        return self._%sWorkspace(args[0], useConfig)

    def _%sWorkspace(self, workspaceName, config=None):
        raise DriverException("Workspace service is not implemented on this driver")
''' % (action, action, action)
    elif name == 'openbexi_dss_proxy/task.py':
        source = replace(source, 'from .common import settings\n', '''from .common import settings
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException


def display_settings(config, workspace=False):
    config = dict(config or {})
    if '_OpenBEXIWorkspace' in config:
        raise DriverException('Reserved driver workspace discriminator')
    span = config.get('Time')
    if isinstance(span, TIME):
        if not span.isRel():
            raise DriverException('Plot time span must be relative')
        config['Time'] = span.rel()
    if workspace:
        config['_OpenBEXIWorkspace'] = True
    return settings(config)
''')
        for action in ('open', 'print', 'close'):
            method = action.title() + 'Display'
            before = "        call('TASK','%s',p.Display(name=name,config=settings(config)))" % method
            source = replace(source, before,
                "        call('TASK','%s',p.Display(name=name,config=display_settings(config)))\n        return True" % method)
        source = replace(source, '\n\nTASK = Tasks()', '''

    def _openWorkspace(self, name, config=None):
        call('TASK', 'OpenDisplay', p.Display(name=name, config=display_settings(config, workspace=True)))
        return True

    def _closeWorkspace(self, name, config=None):
        call('TASK', 'CloseDisplay', p.Display(name=name, config=display_settings(config, workspace=True)))
        return True


TASK = Tasks()''')
    elif name == 'openbexi_spell_dss/ground.py':
        source = replace(source, "        if family == 'TASK':\n", """        if family == 'TASK':
            if method in {'OpenDisplay', 'PrintDisplay', 'CloseDisplay'}:
                from .displays import Displays
                return Displays(self).prepare(method, request.name, settings, check)
""")
    elif name == 'openbexi_spell_dss/rpc.py':
        source = replace(source, 'self.journal.begin(identity, request_id, path, raw)',
                         "self.journal.begin(identity, request_id, path, raw, validate=getattr(action, 'validate', None))")
    else:
        source = replace(source, 'def begin(self, identity, request_id, method, payload):',
                         'def begin(self, identity, request_id, method, payload, *, validate=None):')
        source = replace(source, "            self.db.execute('INSERT INTO effects VALUES(?,?,?,?,?,?,?,?)',", """            # A known invalid state has no effect intent. Receipted duplicates
            # return above without rechecking state changed by their first call.
            if validate is not None:
                validate()
            self.db.execute('INSERT INTO effects VALUES(?,?,?,?,?,?,?,?)',""")
    result = source.encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    manifest = {}
    for name, expected in PREIMAGES.items():
        target = site / name
        original = target.read_bytes()
        patched = apply(name, original)
        for label, content in (('original', original), ('patched', patched)):
            retained = evidence / label / name
            retained.parent.mkdir(parents=True, exist_ok=True)
            retained.write_bytes(content)
        target.write_bytes(patched)
        manifest[name] = dict(preimage_sha256=expected, sha256=hashlib.sha256(patched).hexdigest())
    (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    apply_tree(sys.argv[1], sys.argv[2])
