"""Checked original TM corrections; preserve upstream code and notices.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lib/adapter/tm.py': 'a61e819a6e8767bced46c31bf32b486e467c9e8f2e04ddf480c504ceacc62084',
    'spell/lib/adapter/expression.py': '3adee1ac91f2a5dc8ffcb052f3b6198595cef328eb44c4d9435cb45334cc4b77',
    'spell/lib/adapter/verifier.py': '2a32881c0de3ee716c8a51aa5e34bfbea731b2948dbdcf4ec813df50bcdd79f7',
    'spell/lang/helpers/tmhelper.py': 'cb9a59b147e1079953b7e625273093ddeebe0515d4140f5514844b162154b832',
    'spell/lang/helpers/basehelper.py': '82297f2de69c3d93633c04c4e3b8695fda22633760a12a040413223d3d26f7d7',
}


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    report = {}
    for name, expected in PREIMAGES.items():
        path = site / name
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, name
        original = evidence / 'original' / name
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(raw)
        source = raw.decode()
        if name.endswith('/tmhelper.py'):
            marker = '        self.__useConfig[Retry] = self.__retry'
            assert source.count(marker) == 1
            source = source.replace(marker, marker + '''
        # Validate Delay before the native WaitFor path or any acquisition.
        from spell.lib.adapter.utctime import TIME
        import math
        delay = self.__useConfig.get(Delay)
        if delay is not None:
            if isinstance(delay, TIME):
                if not delay.isRel():
                    raise SyntaxException("Delay must be relative")
                delay = delay.rel()
            if type(delay) not in (int, float) or not math.isfinite(delay) or delay < 0:
                raise SyntaxException("Delay must be finite nonnegative seconds or relative TIME")
''')
            marker = '        self._write("Retry verification", {Severity:WARNING} )'
            assert source.count(marker) == 1
            source = source.replace(marker, marker + '\n        self.__useConfig[Wait] = True')
        elif name.endswith('/basehelper.py'):
            old = '            if (actionResult != result): result = actionResult'
            assert source.count(old) == 1
            source = source.replace(old, '''            # An explicit action replaces the composite payload even when
            # its Boolean value compares equal (for example CANCEL on False).
            result = actionResult''')
        elif not name.endswith('/verifier.py'):
            assert source.count('.isAlive()') == 1
            source = source.replace('.isAlive()', '.is_alive()')
        else:
            marker = '        # Check wether first element is a param name or a tm item'
            assert source.count(marker) == 1
            source = source.replace(marker, '''        if self.__comparison not in (eq, neq, lt, le, gt, ge, bw, nbw):
            raise SyntaxException("Unknown verification comparison operator")
        length = len(parameters) - (1 if type(parameters[-1]) is dict else 0)
        expected = 4 if self.__comparison in (bw, nbw) else 3
        if length != expected:
            raise SyntaxException("Wrong number of verification comparison values")

''' + marker)
        if name.endswith('/tm.py'):
            old = '            if self.__useConfig.get(PromptUser)!=False:'
            assert source.count(old) == 1
            source = source.replace(old, '            if self.__useConfig.get(PromptUser)!=False and self.__useConfig.get(OnFalse)!=NOACTION:')
            old = '''        counter = retries
        if counter < 1:
            counter = 1
        return counter'''
            assert source.count(old) == 1
            source = source.replace(old, '''        if type(retries) is not int or retries < 0:
            raise DriverException("Retries must be a nonnegative integer")
        # LRM 2.4.4 p.42: the initial attempt plus this many repetitions.
        return retries + 1''')
            begin = source.index('def _float_eq(')
            end = source.index('\n# def __old_eq', begin)
            source = source[:begin] + '''def _float_eq(a, b, rel_tol=INTERFACE_DEFAULTS[RelTolerance], abs_tol=0.0):
    # An exactly representable float32 value does not establish the source
    # width. Do not round a double/string comparison target to float32.
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return False
    if a == b:
        return True
    tolerance = max(rel_tol * max(abs(a), abs(b)), abs_tol)
    # LRM tolerance is the inclusive interval around the expected value.
    return b - tolerance <= a <= b + tolerance
''' + source[end:]
        path.write_bytes(source.encode())
        patched = evidence / 'patched' / name
        patched.parent.mkdir(parents=True, exist_ok=True)
        patched.write_bytes(path.read_bytes())
        report[name] = {'preimage_sha256': expected, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (evidence / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    apply_tree(sys.argv[1], sys.argv[2])
