"""Preserve typed database keys and nested TIME literals from LRM p83."""
# SPDX-License-Identifier: LGPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES={
    'spell/lib/adapter/databases/dbfile.py':'6005af75f09953c6f262b07376a57ead5228cff99945a5311a0a3da5837f8618',
    'spell/lib/adapter/databases/database.py':'2d43696843c0f7492137c925474a545429686cebdaf1f219a7c64af5020f7ba0',
    'spell/utils/vimport.py':'95f1ad13d5a58ccc6c5d41d526d605d35074410d95f6d4a799212fbe5474abc9',
}


def replace(source,before,after,count=1):
    if source.count(before)!=count:raise ValueError('Database format anchor differs: '+before[:60])
    return source.replace(before,after)


def method(source,name,body):
    start=source.index('    def '+name+'(')
    end=source.index('    #===========================================================================',start)
    return source[:start]+body+'\n\n'+source[end:]


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Database format preimage differs: '+name)
    source=raw.decode('utf-8')
    if name.endswith('/database.py'):
        # Dict membership validates hashability before changing the key list.
        source=replace(source,'if not key in list(self._properties.keys()):','if key not in self._properties:',2)
    elif name.endswith('/vimport.py'):
        source=replace(source,"'PROC' : PROC,'os':os,'True':True,'False':False",
            "'PROC' : PROC,'os':os,'True':True,'False':False,'TIME':TIME")
    else:
        source=replace(source,'import sys,os,stat,tempfile,math','import sys,os,stat,tempfile,math,ast,io,tokenize')
        source=method(source,'_readData',r'''    def _readData(self):
        with open(self._filename, encoding='utf-8') as stream:
            lines = stream.readlines()
        # Parse into private state; malformed input cannot damage a loaded DB.
        keys, properties, formats = [], {}, {}
        pending = None
        for line in lines:
            text = pending[:-1].strip() + line.strip() if pending else line.strip()
            if not text or text.startswith('#'):
                pending = None
                continue
            if text.endswith('\\'):
                pending = text
                continue
            pending = None
            if text[0] in ('"', "'"):
                token = next(tokenize.generate_tokens(io.StringIO(text).readline))
                if token.type != tokenize.STRING or token.end[0] != 1:
                    raise DriverException('Invalid quoted database key')
                key = ast.literal_eval(token.string)
                rest = text[token.end[1]:]
                if rest and not rest[0].isspace():
                    raise DriverException('Database key must be separated from its value')
                original = rest.lstrip()
            else:
                fields = text.split(None, 1)
                key, unused = ImportValue(fields[0])
                original = fields[1] if len(fields) > 1 else ''
            hash(key)
            value, kind = ImportValue(original)
            if key in properties:
                LOG('WARNING: duplicated database key: ' + repr(key))
                continue
            keys.append(key)
            properties[key] = value
            if kind:formats[key] = kind
        if pending:
            raise DriverException('Unfinished database continuation')
        self._vkeys, self._properties, self._types = keys, properties, formats''')
        source=method(source,'_writeData',r'''    def _writeData(self, theFile):
        def literal(value, ancestors):
            kind = type(value)
            if isinstance(value, TIME):
                return 'TIME(' + repr(ExportValue(value, TIME)) + ')'
            if kind in (str, int, bool, type(None)):
                return repr(value)
            if kind is float and math.isfinite(value):
                return repr(value)
            if kind not in (list, tuple, dict) or id(value) in ancestors:
                raise DriverException('Unsupported database literal value')
            ancestors = ancestors | {id(value)}
            if kind is dict:
                return '{' + ', '.join(literal(key, ancestors) + ': ' + literal(item, ancestors)
                                      for key, item in value.items()) + '}'
            items = ', '.join(literal(item, ancestors) for item in value)
            if kind is list:return '[' + items + ']'
            return '(' + items + (',' if len(value) == 1 else '') + ')'

        def key_text(key):
            if type(key) is str:
                if not key or key.startswith('#'):
                    raise DriverException('Database keys cannot be empty or begin with a comment prefix')
                parsed, unused = ImportValue(key)
                if (type(parsed) is str and parsed == key and not any(c.isspace() for c in key)
                        and key[0] not in ('"', "'")):
                    return key
                return repr(key)
            if type(key) in (int, bool, type(None)) or type(key) is float and math.isfinite(key):
                return repr(key)
            raise DriverException('Unsupported database key type')

        lines = []
        for key in self._vkeys:
            serialized_key = key_text(key)
            value = self._properties[key]
            if isinstance(value, TIME):
                value = ExportValue(value, TIME)
            else:
                encoded = literal(value, set())
                value = ExportValue(value, self._types[key]) if key in self._types else encoded
            if not isinstance(value, str):
                raise DriverException('Database value cannot be serialized: ' + repr(key))
            lines.append(serialized_key + '\t' + value + '\n')
        data = memoryview(''.join(lines).encode('utf-8'))
        while data:
            count = os.write(theFile, data)
            if count <= 0:raise OSError('Database write made no progress')
            data = data[count:]''')
    result=source.encode('utf-8');compile(result,name,'exec');return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    changes={name:((site/name).read_bytes(),apply(name,(site/name).read_bytes())) for name in PREIMAGES}
    manifest={}
    for name,(before,after) in changes.items():
        for label,data in (('original',before),('patched',after)):
            target=evidence/label/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        (site/name).write_bytes(after)
        manifest[name]=dict(preimage_sha256=hashlib.sha256(before).hexdigest(),sha256=hashlib.sha256(after).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    import sys
    apply_tree(sys.argv[1],sys.argv[2])
