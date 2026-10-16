"""Persistent GENERIC display applications and printable telemetry documents.

The profile has virtual DSS/DSS_AUX workstations, two monitors per workstation,
and a durable DSS_REPORTS spool. It does not claim a physical monitor or printer.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
from html import escape
import math
import time
from google.protobuf.empty_pb2 import Empty
from .journal import canonical


DISPLAYS = {'DSS_TELEMETRY': 'alphanumeric', 'DSS_TREND': 'plot',
            'Displays/Telemetría': 'alphanumeric'}
WORKSPACES = {'DSS_WORKSPACE': ('DSS_TELEMETRY', 'DSS_TREND'),
              'Workspaces/Operación': ('Displays/Telemetría', 'DSS_TREND')}
HOSTS = ('DSS', 'DSS_AUX')
WORKSPACE_KEY = '_OpenBEXIWorkspace'
MAX_INSTANCES = 16
MAX_JOBS = 64


def values(snapshot):
    """Render the acquired values, validity and acquisition times, not canned data."""
    return [(str(row['item_id']), str(row['engineering']['value']),
             str(row['validity']), str(row['acquired_at_unix_ns']))
            for row in snapshot['samples']]


def ascii_document(display, snapshot):
    rows = [('ITEM', 'ENGINEERING', 'VALIDITY', 'ACQUIRED_UNIX_NS'), *values(snapshot)]
    text = 'DISPLAY\t' + display + '\n' + '\n'.join('\t'.join(row) for row in rows) + '\n'
    # VECTOR in LRM 2.4.4 is ASCII. Keep every Unicode codepoint recoverable.
    return text.encode('ascii', 'backslashreplace').decode('ascii')


def postscript_document(display, snapshot, span_seconds=60):
    def literal(text):
        raw = text.encode('ascii', 'backslashreplace')
        return ''.join(chr(c) if 32 <= c <= 126 and chr(c) not in '()\\'
                       else '\\%03o' % c for c in raw)
    if DISPLAYS[display] == 'plot':
        end = max(row['acquired_at_unix_ns'] for row in snapshot['samples']) / 1e9
        numeric = [(name, float(value)) for name, value, _, _ in values(snapshot) if _numeric(value)]
        maximum = max([abs(value) for _, value in numeric] + [1.0])
        out = ['%!PS-Adobe-3.0', '%%Creator: OpenBEXI GENERIC display application',
               '%%Pages: 1', '%%BoundingBox: 0 0 842 595', '%%EndComments', '%%Page: 1 1',
               '/Courier findfont 9 scalefont setfont',
               '40 570 moveto (' + literal(display) + ') show',
               'newpath 40 80 moveto 40 520 lineto 800 520 lineto stroke',
               'newpath 40 80 moveto 800 80 lineto stroke']
        for name, value in numeric:
            out.append('newpath 795 %.6f 3 0 360 arc fill' % (300 + value / maximum * 200))
        for x, timestamp in ((40, end - span_seconds), (565, end)):
            stamp = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            out.append('%d 55 moveto (%s) show' % (x, literal(stamp)))
        out.append('40 30 moveto (Initial time span: %.6f seconds) show' % span_seconds)
        return '\n'.join([*out, 'showpage', '%%EOF', ''])
    lines = ascii_document(display, snapshot).splitlines()
    pages = [lines[i:i+48] for i in range(0, len(lines), 48)]
    out = ['%!PS-Adobe-3.0', '%%Creator: OpenBEXI GENERIC display application',
           '%%Pages: ' + str(len(pages)), '%%BoundingBox: 0 0 842 595',
           '%%EndComments', '/Courier findfont 8 scalefont setfont']
    for index, page in enumerate(pages, 1):
        out.append('%%%%Page: %d %d' % (index, index))
        for line, text in enumerate(page):
            out.append('20 %d moveto (%s) show' % (575 - line * 11, literal(text.expandtabs(20))))
        out.append('showpage')
    return '\n'.join([*out, '%%EOF', ''])


def snapshot_for(record, state):
    return record['snapshot'] if 'snapshot' in record else state['display_snapshots'][record['snapshot_sha256']]


def screen(display, record, state=None):
    title = escape(display)
    snapshot = snapshot_for(record, state or {})
    if record['kind'] == 'alphanumeric':
        rows = ''.join('<tr>' + ''.join('<td>' + escape(value) + '</td>' for value in row) + '</tr>'
                       for row in values(snapshot))
        body = '<table><thead><tr><th>Item</th><th>Engineering</th><th>Validity</th><th>Acquired ns</th></tr></thead><tbody>' + rows + '</tbody></table>'
    else:
        end = record['acquired_at_unix_ns'] / 1e9
        start = end - record['span_seconds']
        labels = [datetime.fromtimestamp(v, timezone.utc).isoformat() for v in (start, end)]
        # A newly opened time plot has one acquired sample per numeric parameter.
        # Its time axis still covers the requested initial span; no history is fabricated.
        numeric = [(row[0], float(row[1])) for row in values(snapshot)
                   if _numeric(row[1])]
        maximum = max([abs(value) for _, value in numeric] + [1.0])
        dots = ''.join('<circle cx="750" cy="%.3f" r="4"><title>%s: %s</title></circle>' %
                       (120 - value / maximum * 90, escape(name), value) for name, value in numeric)
        body = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 270" role="img" '
                'aria-label="Telemetry time plot"><path d="M40 20 V220 H760" fill="none" stroke="black"/>'
                + dots + '<text x="40" y="245">' + escape(labels[0]) + '</text>'
                '<text x="470" y="265">' + escape(labels[1]) + '</text></svg>')
    return '<section data-display="' + title + '"><h2>' + title + '</h2>' + body + '</section>'


def _numeric(value):
    try:
        return math.isfinite(float(value))
    except ValueError:
        return False


class Displays:
    def __init__(self, ground):
        self.ground = ground

    @staticmethod
    def applications(state):
        if 'display_applications' in state:
            return state['display_applications']
        # Preserve displays opened by the previous snapshot-only implementation.
        legacy = state.get('displays', {})
        displays = {name: dict(kind=DISPLAYS[name], snapshot=snapshot, span_seconds=60,
                               acquired_at_unix_ns=max(row['acquired_at_unix_ns'] for row in snapshot['samples']))
                    for name, snapshot in legacy.items() if name in DISPLAYS}
        return {'1': dict(id='1', host='DSS', monitor=1, displays=displays, workspaces={})} if displays else {}

    def prepare(self, method, name, settings, check):
        options = dict(settings)
        workspace = options.pop(WORKSPACE_KEY, False)
        if type(workspace) is not bool or (workspace and method == 'PrintDisplay'):
            raise ValueError('PrintDisplay does not accept workspace names')
        catalog = WORKSPACES if workspace else DISPLAYS
        if type(name) is not str or name not in catalog:
            raise ValueError('Unknown GENERIC ' + ('workspace' if workspace else 'display'))
        allowed = {'Host', 'Delay'}
        if method == 'OpenDisplay':
            allowed |= {'Monitor', 'Reuse'} | (set() if workspace else {'Time'})
        elif method == 'PrintDisplay':
            allowed |= {'Printer', 'Format'}
        elif method != 'CloseDisplay':
            raise ValueError('Unknown display operation')
        if set(options) - allowed:
            raise ValueError('Unsupported display modifier: ' + ','.join(sorted(set(options) - allowed)))
        host = options.get('Host', 'DSS')
        if type(host) is not str or host not in HOSTS:
            raise ValueError('Unknown GENERIC workstation')
        monitor = options.get('Monitor', 1)
        if type(monitor) is not int or monitor not in (1, 2):
            raise ValueError('GENERIC monitor must be 1 or 2')
        reuse = options.get('Reuse', True)
        if type(reuse) is not bool:
            raise ValueError('Reuse must be boolean')
        span = options.get('Time', 60)
        if type(span) not in (int, float) or not math.isfinite(span) or not 0 < span <= 86400:
            raise ValueError('Plot time span must be positive, finite, and at most one day')
        if 'Time' in options and DISPLAYS.get(name) != 'plot':
            raise ValueError('Time applies to telemetry plots')
        fmt = options.get('Format', 'PS')
        if type(fmt) is not str or fmt.upper() not in ('PS', 'VECTOR'):
            raise ValueError('Display format must be PS or VECTOR')
        fmt = fmt.upper()
        if method == 'PrintDisplay' and fmt == 'VECTOR' and DISPLAYS[name] != 'alphanumeric':
            raise ValueError('VECTOR requires an alphanumeric display')
        printer = options.get('Printer', '')
        if type(printer) is not str or printer not in ('', 'DSS_REPORTS'):
            raise ValueError('Unknown GENERIC printer')
        delay = options.get('Delay', 0)
        if type(delay) not in (int, float) or not math.isfinite(delay) or not 0 <= delay <= 30:
            raise ValueError('Display completion delay must be finite and between zero and 30 seconds')
        names = WORKSPACES[name] if workspace else (name,)

        def validate_state(state):
            apps = self.applications(state)
            matching = [app for app in apps.values() if app['host'] == host]
            if method == 'OpenDisplay':
                can_reuse = reuse and any(app['monitor'] == monitor for app in matching)
                if not can_reuse and len(apps) >= MAX_INSTANCES:
                    raise ValueError('GENERIC display application capacity exceeded')
            elif method == 'CloseDisplay':
                if not any(name in app['workspaces' if workspace else 'displays'] for app in matching):
                    raise ValueError(('Workspace' if workspace else 'Display') + ' is not open on workstation')
            else:
                if not any(name in app['displays'] for app in matching):
                    raise ValueError('Display is not open on workstation')
                if len(state.get('display_jobs', {})) >= MAX_JOBS:
                    raise ValueError('GENERIC print spool capacity exceeded')

        def operate():
            check()
            self.ground.update(update)
            # Original language.xml supplies launch/print/close settling delays.
            # Preserve those defaults and remain responsive to authority loss.
            deadline = time.monotonic() + delay
            while True:
                check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.ground.transport.stop.wait(min(.025, remaining)):
                    raise RuntimeError('Display transport closed during completion delay')
            return Empty()

        captured = {}

        def update(state):
            snapshot = captured['snapshot']
            validate_state(state)
            apps = state.setdefault('display_applications', self.applications(state))
            if apps:
                state['display_application_sequence'] = max(
                    state.get('display_application_sequence', 0), max(map(int, apps)))
            jobs = state.setdefault('display_jobs', {})
            snapshots = state.setdefault('display_snapshots', {})
            snapshot_hash = hashlib.sha256(canonical(snapshot).encode('utf-8')).hexdigest() if snapshot is not None else None
            if snapshot_hash is not None:
                snapshots.setdefault(snapshot_hash, snapshot)
            matching = [app for app in apps.values() if app['host'] == host]
            if method == 'OpenDisplay':
                candidates = [app for app in matching if app['monitor'] == monitor]
                if reuse and candidates:
                    app = max(candidates, key=lambda item: int(item['id']))
                else:
                    if len(apps) >= MAX_INSTANCES:
                        raise ValueError('GENERIC display application capacity exceeded')
                    number = state.get('display_application_sequence', 0) + 1
                    state['display_application_sequence'] = number
                    app = dict(id=str(number), host=host, monitor=monitor, displays={}, workspaces={})
                    apps[app['id']] = app
                for display in names:
                    app['displays'][display] = dict(kind=DISPLAYS[display], snapshot_sha256=snapshot_hash,
                        span_seconds=span, acquired_at_unix_ns=max(
                            row['acquired_at_unix_ns'] for row in snapshot['samples']))
                if workspace:
                    app['workspaces'][name] = list(names)
            elif method == 'CloseDisplay':
                selected = [app for app in matching if name in app['workspaces' if workspace else 'displays']]
                if not selected:
                    raise ValueError(('Workspace' if workspace else 'Display') + ' is not open on workstation')
                for app in selected:
                    for display in names:
                        app['displays'].pop(display, None)
                    # A partially closed workspace is no longer an open workspace.
                    app['workspaces'] = {key: members for key, members in app['workspaces'].items()
                                         if all(member in app['displays'] for member in members)}
                    if not app['displays']:
                        del apps[app['id']]
            else:
                selected = [app for app in matching if name in app['displays']]
                if not selected:
                    raise ValueError('Display is not open on workstation')
                if len(jobs) >= MAX_JOBS:
                    raise ValueError('GENERIC print spool capacity exceeded')
                number = state.get('display_job_sequence', 0) + 1
                state['display_job_sequence'] = number
                app = max(selected, key=lambda item: int(item['id']))
                print_span = app['displays'][name]['span_seconds']
                content = (postscript_document(name, snapshot, print_span) if fmt == 'PS'
                           else ascii_document(name, snapshot))
                job = dict(id=str(number), display=name, host=host, printer=printer, format=fmt,
                    media_type='application/postscript' if fmt == 'PS' else 'text/plain',
                    content=content, status='SPOOLED' if printer else 'FILE', snapshot_sha256=snapshot_hash,
                    application=app['id'], span_seconds=print_span)
                jobs[job['id']] = job
                state['reports']['display-' + name] = job
            referenced = {row['snapshot_sha256'] for app in apps.values() for row in app['displays'].values()
                          if 'snapshot_sha256' in row}
            referenced.update(job['snapshot_sha256'] for job in jobs.values() if 'snapshot_sha256' in job)
            state['display_snapshots'] = {key: value for key,value in snapshots.items() if key in referenced}

        def validate():
            validate_state(self.ground.state())
            captured['snapshot'] = self.ground.transport.get('telemetry') if method != 'CloseDisplay' else None
            # Preview the same pure state transition before recording an intent.
            # The shared ground journal has its own byte budget in addition to
            # the application/job count bounds; known capacity failures are safe.
            planned = deepcopy(self.ground.state())
            update(planned)
            if (len(canonical(planned)) > 1024 * 1024
                    or any(len(planned[key]) > 128 for key in
                           ('resources', 'limits', 'injections', 'images', 'reports', 'displays', 'users'))):
                raise ValueError('Simulator ground service capacity exceeded')
        # Journal executes this under its transaction, after duplicate/fence
        # checks and before a new intent. A rejected request cannot poison a run.
        operate.validate = validate
        return operate


def document(state):
    apps = state.get('display_applications', {})
    sections = []
    for app in apps.values():
        label = escape('%s / monitor %s / application %s' % (app['host'], app['monitor'], app['id']))
        sections.append('<article data-application="' + escape(app['id']) + '"><h1>' + label + '</h1>'
                        + ''.join(screen(name, record, state) for name, record in app['displays'].items()) + '</article>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>GENERIC GCS displays</title>'
            '<style>body{font:16px sans-serif;margin:2rem}article{border:1px solid #888;padding:1rem;margin:1rem 0}'
            'table{border-collapse:collapse}th,td{border:1px solid #aaa;padding:.3rem;text-align:left}'
            'svg{max-width:100%;width:800px}circle{fill:#075ea8}</style><body>'
            + ''.join(sections) + '</body></html>')
