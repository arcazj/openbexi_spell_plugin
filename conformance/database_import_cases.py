"""Configured native database file contracts, LRM 2.4.4 pp78-80."""
CASES = {}
GROUND = "DECODER CMD_ACT_DEC\nDECODER_CALIBRATION {0:'DEC1',1:'DEC2'}\n"
SPACECRAFT = "SC 'Test spacecraft'\nSpacecraft_Name 'Test spacecraft'\n"


def add(group, contracts, dimension, source, ground=GROUND, spacecraft=SPACECRAFT):
    CASES[group + ':' + dimension] = dict(source=source, ground=ground, spacecraft=spacecraft,
        contracts=['CMP-LRM244-' + item for item in contracts], dimension=dimension,
        oracle='Original native executor startup loads real configured UTF-8 database files; the procedure reads the original runtime database objects.')


GDB = ('DATABASE-GDB', 'EXAMPLE-139')
add('ground', GDB, 'positive', """
assert GDB['DECODER'] == 'CMD_ACT_DEC'
assert GDB['DECODER_CALIBRATION'] == {0:'DEC1', 1:'DEC2'}
assert type(GDB['DECODER_CALIBRATION']) is dict
assert GDB['DECODER_CALIBRATION'][0] == 'DEC1'
assert GDB['DECODER_CALIBRATION'][1] == 'DEC2'
""")
add('ground', GDB, 'boundary', """
expected = {'ZERO':0, 'FALSE':False, 'EMPTY_TEXT':'', 'EMPTY_LIST':[], 'EMPTY_DICT':{},
            'BIG':2**80, 'NEGATIVE':-2.5, 'UNICODE':'caf\u00e9 \u03bb', 'NESTED':{'items':[False, 0]}}
for key, value in expected.items():
    assert GDB[key] == value, (key, GDB[key])
    assert type(GDB[key]) is type(value), key
assert GDB['DECODER_CALIBRATION'] == {0:'DEC1',1:'DEC2'}
""", ground=GROUND+"ZERO 0\nFALSE False\nEMPTY_TEXT ''\nEMPTY_LIST []\nEMPTY_DICT {}\nBIG 1208925819614629174706176\nNEGATIVE -2.5\nUNICODE 'café λ'\nNESTED {'items':[False,0]}\n")
add('ground', GDB, 'failure', """
rejects(DriverException, lambda: GDB['missing'])
rejects(KeyError, lambda: GDB['DECODER_CALIBRATION'][2])
rejects(TypeError, lambda: GDB[[]])
""")
add('ground', GDB, 'recovery', """
rejects(DriverException, lambda: GDB['missing'])
rejects(TypeError, lambda: GDB[[]])
assert GDB['DECODER'] == 'CMD_ACT_DEC'
assert GDB['DECODER_CALIBRATION'][0] == 'DEC1'
assert GDB['DECODER_CALIBRATION'][1] == 'DEC2'
""")

add('spacecraft-lookup', ('EXAMPLE-135',), 'positive', "assert SCDB['SC'] == 'Test spacecraft'")
add('spacecraft-lookup', ('EXAMPLE-135',), 'boundary', "assert SCDB['SC'] == 'caf\u00e9 \u03bb'", spacecraft="SC 'café λ'\n")
add('spacecraft-lookup', ('EXAMPLE-135',), 'failure', "rejects(DriverException, lambda: SCDB['missing'])")
add('spacecraft-lookup', ('EXAMPLE-135',), 'recovery', "rejects(DriverException, lambda: SCDB['missing']); assert SCDB['SC'] == 'Test spacecraft'")

add('spacecraft-keys', ('EXAMPLE-136',), 'positive', "assert list(SCDB.keys()) == ['SC','Spacecraft_Name']")
add('spacecraft-keys', ('EXAMPLE-136',), 'boundary', "assert list(SCDB.keys()) == []", spacecraft='# Empty configured spacecraft database\n')
add('spacecraft-keys', ('EXAMPLE-136',), 'failure', "rejects(TypeError, lambda: SCDB.keys('unexpected'))")
add('spacecraft-keys', ('EXAMPLE-136',), 'recovery', "rejects(TypeError, lambda: SCDB.keys('unexpected')); assert list(SCDB.keys()) == ['SC','Spacecraft_Name']")

add('spacecraft-existence', ('EXAMPLE-137',), 'positive', "assert SCDB.has_key('Spacecraft_Name') is True")
add('spacecraft-existence', ('EXAMPLE-137',), 'boundary', "assert SCDB.has_key('Spacecraft_Name') is False", spacecraft='# Empty configured spacecraft database\n')
add('spacecraft-existence', ('EXAMPLE-137',), 'failure', "rejects(TypeError, lambda: SCDB.has_key())")
add('spacecraft-existence', ('EXAMPLE-137',), 'recovery', "rejects(TypeError, lambda: SCDB.has_key()); assert SCDB.has_key('Spacecraft_Name') is True")
