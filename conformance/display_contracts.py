"""Execute real native helpers and compare separately observed GCS state and files."""
import hashlib
import json
from pathlib import Path
import time
from xml.etree import ElementTree
from datetime import datetime

from spell.lang.functions import OpenDisplay, CloseDisplay, PrintDisplay, OpenWorkspace, CloseWorkspace
from spell.lang.modifiers import Host, Monitor, Reuse, Time, Format, Printer
from spell.lang.constants import PS, VECTOR
from spell.lib.adapter.utctime import TIME, HOUR
from spell.lib.exception import SpellException

ALPHA, PLOT, WORKSPACE = 'DSS_TELEMETRY', 'DSS_TREND', 'DSS_WORKSPACE'
UNICODE_ALPHA, UNICODE_WORKSPACE = 'Displays/Telemetría', 'Workspaces/Operación'
CFG = dict(HandleError=False, PromptUser=False, Delay=0)
calls = []


def fixture(action, **values):
    token = str(time.monotonic_ns())
    target = Path('fixture-request.json')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(token=token, action=action, **values)), encoding='utf-8')
    temporary.replace(target)
    reply = Path('fixture-' + token + '.json')
    deadline = time.monotonic() + 15
    while not reply.exists():
        if time.monotonic() > deadline:
            raise TimeoutError('Display observer did not respond')
        time.sleep(.01)
    result = json.loads(reply.read_bytes())
    assert 'error' not in result, result
    return result


def equal(actual, expected):
    assert actual == expected, (actual, expected)


def mark():
    return fixture('observe')


def apps():
    return mark()['ground']['display_applications']


def one_app():
    app, = apps().values()
    return app


def good(function, target, **options):
    defaults = ({'Delay': 6, 'Format': 'ps'} if function is PrintDisplay else
                {'Delay': 6} if function is OpenDisplay else {'Delay': 3} if function is CloseDisplay else {})
    effective = {**defaults, **{key:value for key,value in CFG.items() if key=='Delay'}, **options}
    began = time.monotonic()
    result = function(target, **dict(CFG, **options))
    calls.append(dict(function=function.__name__, target=target, options={k: str(v) for k,v in effective.items()},
                      explicit_options={k: str(v) for k,v in options.items()}, seconds=time.monotonic()-began,
                      returned=result, return_type=type(result).__name__))
    assert result is True, calls[-1]


def good_default(function, target, **options):
    previous = CFG.pop('Delay')
    try:
        good(function, target, **options)
        assert calls[-1]['seconds'] >= float(calls[-1]['options']['Delay'])
    finally:
        CFG['Delay'] = previous


def bad(function, target, **options):
    before = mark()
    try:
        result = function(target, **dict(CFG, **options))
    except (SpellException, TypeError, ValueError) as error:
        calls.append(dict(function=function.__name__, target=target, options={k: str(v) for k,v in options.items()},
                          error_type=type(error).__name__, error=str(error)))
    else:
        raise AssertionError(('Invalid display request returned', result))
    after = mark()
    equal(after['ground'], before['ground'])
    equal(after['effects'], before['effects'])


def last_job():
    state = mark()['ground']
    jobs = state['display_jobs']
    job = jobs[max(jobs, key=int)]
    return dict(job, snapshot=state['display_snapshots'][job['snapshot_sha256']])


def print_document(job, fmt, spooled):
    equal(job['snapshot'], mark()['telemetry'])
    equal(job['format'], fmt)
    equal(job['status'], 'SPOOLED' if spooled else 'FILE')
    equal(job['printer'], 'DSS_REPORTS' if spooled else '')
    content = job['content']
    assert content.isascii()
    if fmt == PS:
        assert content.startswith('%!PS-Adobe-3.0\n') and content.endswith('%%EOF\n')
        assert '%%Page: 1 1\n' in content and 'showpage' in content
    else:
        assert content.startswith('DISPLAY\t') and '\tENGINEERING\tVALIDITY\t' in content
        for sample in job['snapshot']['samples']:
            assert sample['item_id'] in content
            assert str(sample['engineering']['value']) in content
    fetched = fixture('download', identity=job['id'])
    equal(fetched['content'], content)
    equal(fetched['sha256'], hashlib.sha256(content.encode('ascii')).hexdigest())
    equal(fetched['media_type'], job['media_type'])


def plot_axis(span):
    observed = mark()
    app, = observed['ground']['display_applications'].values()
    record = app['displays'][PLOT]
    equal(observed['ground']['display_snapshots'][record['snapshot_sha256']], observed['telemetry'])
    markup = fixture('viewer')['html']
    start = markup.index('<svg ')
    end = markup.index('</svg>', start) + len('</svg>')
    root = ElementTree.fromstring(markup[start:end])
    labels = [node.text for node in root.iter('{http://www.w3.org/2000/svg}text')]
    equal((datetime.fromisoformat(labels[1])-datetime.fromisoformat(labels[0])).total_seconds(),span)
    assert list(root.iter('{http://www.w3.org/2000/svg}circle'))


def run():
    cases = json.loads(Path('cases.json').read_bytes())
    checks = {}
    for name, spec in cases.items():
        temporary = Path('current.tmp')
        temporary.write_text(json.dumps(dict(check=name)), encoding='utf-8')
        temporary.replace('current.json')
        calls.clear()
        began = time.monotonic()
        try:
            before = fixture('reset')
            exec(compile(spec['source'], 'GCS_DISPLAY:' + name, 'exec'), globals(), globals())
            after = mark()
            checks[name] = dict(passed=True, before=before, after=after)
        except Exception as error:
            checks[name] = dict(passed=False, error=type(error).__name__ + ': ' + str(error))
        checks[name].update(spec, calls=list(calls), seconds=time.monotonic()-began)
        Path('checks.json').write_text(json.dumps(checks, indent=2)+'\n', encoding='utf-8')
    assert all(row['passed'] for row in checks.values()), {k:v.get('error') for k,v in checks.items() if not v['passed']}
