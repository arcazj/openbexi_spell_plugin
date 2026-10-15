"""Native diagnostics for the database-value grammar on LRM p83."""
from database_import_cases import GROUND, SPACECRAFT

CASES = {}


def add(name, source, values=''):
    CASES[name] = dict(source=source, ground=GROUND + values, spacecraft=SPACECRAFT,
        contracts=[], oracle='Literal numeric expectations from LRM p83 through configured DatabaseFile loading; no inventory promotion.')


add('octal-values', """
assert GDB['OCTAL'] == 29 and type(GDB['OCTAL']) is int
""", 'OCTAL 035\n')
add('octal-boundaries', """
expected = {'ZERO':0, 'ZEROS':0, 'MAX_DIGIT':7, 'NEGATIVE':-29, 'POSITIVE':29,
            'LARGE':1208925819614629174706176}
for key,value in expected.items():
    assert type(GDB[key]) is int and GDB[key] == value, (key, repr(GDB[key]))
""", 'ZERO 0\nZEROS 000\nMAX_DIGIT 07\nNEGATIVE -035\nPOSITIVE +035\nLARGE 04000000000000000000000000000\n')
add('non-octal-text', """
assert GDB['TEXT'] == '035' and type(GDB['TEXT']) is str
assert GDB['NOT_OCTAL'] == '038' and type(GDB['NOT_OCTAL']) is str
assert GDB['DECIMAL'] == 35 and type(GDB['DECIMAL']) is int
""", "TEXT '035'\nNOT_OCTAL 038\nDECIMAL 35\n")
add('import-recovery', """
from spell.utils.vimport import ImportValue
rejects(ValueError, lambda: ImportValue('0b2'))
assert ImportValue('035')[0] == 29
assert GDB['OCTAL'] == 29
""", 'OCTAL 035\n')
add('binary-type', """
from spell.utils.vimport import ImportValue, ExportValue
value,kind = ImportValue('0b001101')
assert value == 13 and type(value) is int
assert ExportValue(value,kind) == '0b001101', (kind, ExportValue(value,kind))
assert GDB['BINARY'] == 13
""", 'BINARY 0b001101\n')
add('hex-type', """
from spell.utils.vimport import ImportValue, ExportValue
value,kind = ImportValue('0xFF')
assert value == 255 and type(value) is int
assert ExportValue(value,kind) == '0xFF'
assert GDB['HEX'] == 255
""", 'HEX 0xFF\n')
