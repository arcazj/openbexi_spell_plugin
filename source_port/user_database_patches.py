"""Preserve user database files across create/save failures (LRM pp81-84).

SPDX-License-Identifier: LGPL-3.0-or-later
Apply after database_import_patches. Original source notices stay in place.
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lib/adapter/databases/dbfile.py': '743b1d290976c37126e1ac0cc6c195948910645ab4e76f756997713cf7ec8095',
    'spell/lang/helpers/filehelper.py': '6d1f9ad5f5ee6f0b473ac650f1f0012fd9644b1ca8beca105ac11257e844a057',
    'spell/utils/vimport.py': '6fe27600fac803b5d17ac5caedf2fb96abccc4451a456f1b0a1772e80b0699fc',
}


def replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected user database replacement count: ' + before[:70])
    return text.replace(before, after)


def method(text, name, body):
    start = text.index('    def ' + name + '(')
    end = text.index('    #===========================================================================', start)
    return text[:start] + body + '\n\n' + text[end:]


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Unexpected user database preimage: ' + name)
    text = raw.decode('utf-8')
    if name.endswith('/dbfile.py'):
        text = replace(text, 'import sys,os', 'import sys,os,stat,tempfile,math\nfrom spell.lib.adapter.utctime import TIME')
        text = method(text, 'create', '''    def create(self):
        try:
            # Exclusive creation must precede resetting a cached dictionary.
            with open(self._filename, 'x', encoding='utf-8'):
                pass
        except Exception as ex:
            raise DriverException('Cannot create database', str(ex))
        super(DatabaseFile, self).__init__()
        return self''')
        text = replace(text, 'if lineToProcess.find("\\\\")!=-1:', 'if lineToProcess.endswith("\\\\"):')
        text = replace(text, '''                key = lineToProcess.split()[0]
                orig_value = " ".join(lineToProcess.split()[1:])''', '''                fields = lineToProcess.split(None, 1)
                key = fields[0]
                orig_value = fields[1] if len(fields) > 1 else ""''')
        text = method(text, '_writeData', '''    def _writeData(self, theFile):
        def literal(value, ancestors):
            kind = type(value)
            if kind in (str, int, bool, type(None)):
                return
            if kind is float and math.isfinite(value):
                return
            if kind not in (list, tuple, dict) or id(value) in ancestors:
                raise DriverException('Unsupported database literal value')
            ancestors = ancestors | {id(value)}
            if kind is dict:
                for key, item in value.items():
                    literal(key, ancestors)
                    literal(item, ancestors)
            else:
                for item in value:
                    literal(item, ancestors)
        lines = []
        for key in self._vkeys:
            if (type(key) is not str or not key or key.startswith('#')
                    or any(c.isspace() for c in key)):
                raise DriverException('Database file keys must be nonempty strings without whitespace or a comment prefix')
            value = self._properties[key]
            if isinstance(value, TIME):
                value = ExportValue(value, TIME)
            else:
                literal(value, set())
                if key in self._types:
                    value = ExportValue(value, self._types[key])
                else:
                    # repr keeps quotes, backslashes, whitespace and nested literals.
                    value = repr(value)
            if not isinstance(value, str):
                raise DriverException('Database value cannot be serialized: ' + key)
            lines.append(key + '\\t' + value + '\\n')
        data = memoryview(''.join(lines).encode('utf-8'))
        while data:
            count = os.write(theFile, data)
            if count <= 0:
                raise OSError('Database write made no progress')
            data = data[count:]''')
        text = method(text, 'commit', '''    def commit(self):
        descriptor, temporary = None, None
        try:
            # Require the existing storage and its write permission. Atomic
            # replacement alone would bypass a read-only file's permission.
            original = os.open(self._filename, os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0))
            try:
                info = os.fstat(original)
                if not stat.S_ISREG(info.st_mode):
                    raise OSError('Database storage is not a regular file')
            finally:
                os.close(original)
            descriptor, temporary = tempfile.mkstemp(prefix='.spell-db-', dir=os.path.dirname(self._filename))
            self._writeData(descriptor)
            os.fchmod(descriptor, stat.S_IMODE(info.st_mode))
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            # All serialization and write failures leave the prior file intact.
            os.replace(temporary, self._filename)
            temporary = None
        except Exception as ex:
            raise DriverException('Cannot write in database', str(ex))
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary is not None:
                os.unlink(temporary)''')
    elif name.endswith('/vimport.py'):
        text = replace(text, '''        elif orig_value.startswith("0") and not "." in orig_value:
            vtype = OCT
        elif orig_value.startswith("0b"):
            len = len(orig_value)-2
            vtype = BIN + str(len)''', '''        elif orig_value.startswith("0b"):
            width = len(orig_value)-2
            vtype = BIN + str(width)
        elif orig_value.startswith("0") and not "." in orig_value:
            vtype = OCT''')
        text = replace(text, '''    if vtype == HEX:''', '''    if isinstance(value, TIME):
        stamp = value.value()
        if not value.isRel():
            return stamp.isoformat(sep=' ', timespec='microseconds')
        micros = (stamp.days * 86400 + stamp.seconds) * 1000000 + stamp.microseconds
        sign = '-' if micros < 0 else '+'
        seconds, fraction = divmod(abs(micros), 1000000)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return '%s%d %02d:%02d:%02d.%06d' % (sign, days, hours, minutes, seconds, fraction)
    if vtype == HEX:''')
    else:
        # WrapperHelper already removes the optional trailing configuration dict.
        for class_name, next_class in [('LoadDictionary','LoadExternalData'), ('SaveDictionary','CreateDictionary'), ('CreateDictionary','OpenFile')]:
            start = text.index('class ' + class_name + '_Helper(')
            end = text.index('class ' + next_class + '_Helper(', start)
            chunk = text[start:end]
            chunk = replace(chunk, 'if len(args)==0:', 'if len(args)!=1:')
            chunk = replace(chunk, 'raise SyntaxException("No dictionary given")', 'raise SyntaxException("Expected exactly one dictionary argument")')
            if class_name in ('LoadDictionary', 'CreateDictionary'):
                anchor = '        idx = self.__database.find("//")\n'
                if chunk.count(anchor) < 1:
                    raise ValueError('Missing dictionary URI validation anchor')
                validation = '''        uri_path = self.__database.split('://', 1)[1]
        if (not uri_path or any(c.isspace() for c in uri_path)
                or any(part in ('', '.', '..') for part in uri_path.replace('\\\\', '/').split('/'))):
            raise SyntaxException('Invalid database path')

'''
                chunk = chunk.replace(anchor, validation + anchor, 1)
            if class_name == 'CreateDictionary':
                chunk = replace(chunk, '''        self._write("Retry creating dictionary", {Severity:WARNING} )
        return [True,None]''', '''        from spell.lang.functions import Prompt
        newName = str(Prompt('Enter new database name: ', Type=ALPHA, Notify=False))
        if '://' not in newName:
            newName = self.__prefix + '://' + newName
        self.__database = newName
        self.__retry = True
        return [True,None]''')
            text = text[:start] + chunk + text[end:]
    result = text.encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    changes = {name: ((site/name).read_bytes(), apply(name, (site/name).read_bytes())) for name in PREIMAGES}
    report = {}
    for name, (before, after) in changes.items():
        for label, content in [('preimage', before), ('patched', after)]:
            target = evidence/label/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (site/name).write_bytes(after)
        report[name] = dict(preimage=hashlib.sha256(before).hexdigest(), sha256=hashlib.sha256(after).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
