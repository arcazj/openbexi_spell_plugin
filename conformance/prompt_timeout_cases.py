"""LRM 2.4.4 pp.71-72: independent timed-default and indefinite-wait cases."""
PREAMBLE = '''import json
import time
from pathlib import Path
from spell.lang.functions import Prompt
from spell.lang.constants import LIST
from spell.lib.exception import SyntaxException
'''
OPTIONS = "['A :Option 1', 'B :Option 2']"
REJECT = '''try:
    Prompt('INVALID_TIMEOUT', ['A:Option 1'], Type=LIST,
           Timeout='invalid', Default='A', HandleError=False)
except SyntaxException:
    Path('rejected.txt').write_text('SyntaxException')
else:
    raise AssertionError('Malformed timeout was accepted')
'''


def timed(default, prefix=''):
    return PREAMBLE + prefix + f'''began=time.monotonic()
answer=Prompt('TIMED_DEFAULT', {OPTIONS}, Type=LIST,
              Default='{default}', Timeout=0.25, HandleError=False)
elapsed=time.monotonic()-began
assert answer == '{default}', repr(answer)
assert elapsed >= 0.25, elapsed
Path('result.json').write_text(json.dumps(dict(answer=answer,elapsed=elapsed)))
'''


def indefinite(timeout, default="Default='A',"):
    return PREAMBLE + f'''answer=Prompt('EXPLICIT_ANSWER', {OPTIONS}, Type=LIST,
              {default} {timeout} HandleError=False)
assert answer == 'B', repr(answer)
Path('result.json').write_text(json.dumps(dict(answer=answer)))
'''


CASES = {
    'default:positive': {'dimension': 'positive', 'source': timed('B'), 'answer': 'B'},
    'default:boundary': {'dimension': 'boundary', 'source': indefinite('Timeout=0,'),
                         'answer': 'B', 'reply': '1', 'hold': 0.35},
    'default:failure': {'dimension': 'failure', 'source': PREAMBLE + REJECT,
                        'rejected': True, 'no_prompt': True},
    'default:recovery': {'dimension': 'recovery', 'source': timed('A', REJECT),
                         'answer': 'A', 'rejected': True},
    'no-timeout:boundary': {'dimension': 'boundary', 'source': indefinite(''),
                            'answer': 'B', 'reply': '1', 'hold': 0.35},
    'no-default:boundary': {'dimension': 'boundary',
                            'source': indefinite('Timeout=0.25,', ''),
                            'answer': 'B', 'reply': '1', 'hold': 0.55,
                            'wire_default': ''},
    'operator:positive': {'dimension': 'positive',
                           'source': indefinite('Timeout=1.5,'),
                           'answer': 'B', 'reply': '1', 'hold': 0.05},
    'duplicate:boundary': {'dimension': 'boundary',
                            'source': indefinite('Timeout=1.5,'),
                            'answer': 'B', 'reply': '1', 'extra_replies': ['0'], 'hold': 0},
    'cancel:failure': {'dimension': 'failure', 'cancel': True, 'hold': 0.05,
                       'expected_status': 'ABORTED', 'source': PREAMBLE + f'''try:
    answer=Prompt('CANCEL_TIMED_DEFAULT', {OPTIONS}, Type=LIST,
                  Default='A', Timeout=1.5, HandleError=False)
    Path('result.json').write_text(json.dumps(dict(answer=answer)))
finally:
    Path('cleanup.txt').write_text('cancelled')
'''},
}
