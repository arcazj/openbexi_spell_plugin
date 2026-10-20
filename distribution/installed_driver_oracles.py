"""Adapt legacy integration oracles to the independently qualified v0.5 contracts.

The uncomposed source-driver tests remain useful for the legacy profile. The
shipped 0.6 wheel applies the reviewed telemetry, command and ranging recipes;
its installed integration test must assert those contracts explicitly.
"""


def adapt(name, source):
    replacements = []
    if name == 'native_driver_acceptance.py':
        replacements = [
            ("for value in (TIME(.000001), TIME(30), .5, 30):",
             "for value in (TIME(.000001), TIME(30), TIME(31), TIME(3600), .5, 30, 3600):"),
            ("TIME(-1),TIME(31),True", "TIME(-1),TIME(3601),True"),
            ("assert Send(command='CMD1',config={Timeout:TIME(2),Confirm:False,PromptUser:False})",
             """# The composed telemetry and command contracts permit one-hour budgets.
for value in (TIME(31), TIME(3600)):
    assert tm._refreshItem(item,{Timeout:value,Wait:False})[1]
assert Send(command='CMD1',config={Timeout:TIME(2),Confirm:False,PromptUser:False})"""),
            ("assert REGISTRY['RNG'].getRangingStatus() == 'RANGING'",
             "from spell.lang.constants import RANGING\nassert RANGING == 1\n"
             "assert REGISTRY['RNG'].getRangingStatus() == RANGING"),
        ]
    elif name == 'test_original_driver.py':
        replacements = [
            ("assert len(calls) == 7",
             "# Composed command routing fences planning and each receipt stage.\n"
             "    assert len(calls) == 13 and all(calls)"),
            ("assert list(ranging.GetBasebandNames(pack({}),timeout=3).names) == ['DSS-BBE-1']",
             "assert list(ranging.GetBasebandNames(pack({}),timeout=3).names) == ['DSS-BBE-1','DSS-BBE-2']"),
        ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Legacy integration oracle anchor changed: ' + name + ': ' + before)
        source = source.replace(before, after)
    return source
