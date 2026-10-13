"""Checked original 2.6.10 DATA/FILES corrections (GPL-3.0-or-later)."""
import hashlib

PREIMAGES = {
    'spell/lib/adapter/file.py': '72b7f18a6fc07d9b6aa4b15ac419e33a7c2f9ce77c5c8b75cf201d5a808e19b3',
    'spell/lang/helpers/filehelper.py': '98577dc51eb604408fae9401f9a203a6612e01a5e004ef112156d87aee3a7d0d',
    'spell/lang/helpers/datahelper.py': '4b571bc724d87f30be4000f612d8edc972ae8147ae0fecfbf5528331cb6cdd5f',
}


def replace(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)


def apply(name, content):
    assert hashlib.sha256(content).hexdigest() == PREIMAGES[name], name
    text = content.decode('utf-8').replace('\r\n', '\n')
    if name.endswith('/file.py'):
        text = replace(text, '    def delete(self):',
            '    # LRM p.92 spellings; retain the original camel-case API.\n'
            '    isdir = isDir\n    isfile = isFile\n\n'
            '    def delete(self):')
        text = replace(text, 'if not os.access(self.dirname(), os.W_OK):',
                       'if not os.access(self.dirname() or os.curdir, os.W_OK):')
        text = replace(text, 'self.__file = open(self.__filename, modeStr)',
                       'self.__file = open(self.__filename, modeStr, encoding="utf-8")')
    elif name.endswith('/filehelper.py'):
        text = replace(text,
            '        if theFile.isDir():\n            raise DriverException("Cannot delete file", "A directory has been provided")\n',
            '        # File.delete implements rmdir: only empty directories can be removed.\n')
        text = replace(text,
            '        if theFile.isDir():\n            raise DriverException("Cannot write to file", "A directory has been provided")',
            '        if type(theData) == list and any(type(item) != str for item in theData):\n'
            '            raise SyntaxException("Expected a list of strings as second argument")\n\n'
            '        if theFile.isDir():\n            raise DriverException("Cannot write to file", "A directory has been provided")')
    elif name.endswith('/datahelper.py'):
        text = replace(text, '        if len(args)==1:\n            # Ensure that the argument is a list',
            '        # LRM Example 180 also permits positional name and value.\n'
            '        if len(args) in (2, 3):\n            args = (list(args),)\n\n'
            '        if len(args)==1:\n            # Ensure that the argument is a list')
        text = replace(text, '            if type(args[0][1])==list:',
            '            if args[0] and type(args[0][0]) == list:')
        text = replace(text, '                    if type(item) != list:',
            '                    if type(item) != list or len(item) not in (2, 3):')
        marker = 'class ClearSharedDataScopes_Helper(WrapperHelper):'
        before, after = text.split(marker)
        after = replace(after,
            '        else:\n            self.__scope = None\n',
            '        elif Scope in useConfig:\n'
            '            self.__scope = useConfig[Scope]\n'
            '            self.delConfig(Scope)\n'
            '            if type(self.__scope) != str:\n'
            '                raise SyntaxException("Expected scope name as string")\n'
            '        else:\n            self.__scope = None\n')
        text = before + marker + after
    result = text.encode('utf-8')
    compile(result, name, 'exec')
    return result
