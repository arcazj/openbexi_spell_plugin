"""Read-only local GCS display application and print spool viewer."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from .displays import document


def journal_state(path, namespace=None):
    """Read an existing ground namespace without creating or migrating its data."""
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        if namespace is None:
            rows = db.execute('SELECT namespace,state FROM ground').fetchall()
            if len(rows) != 1:
                raise ValueError('Select one ground namespace using --namespace')
        else:
            rows = db.execute('SELECT namespace,state FROM ground WHERE namespace=?', (namespace,)).fetchall()
            if not rows:
                raise ValueError('Ground namespace does not exist')
        return json.loads(rows[0][1])


def create_server(read_state, port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                state = read_state()
                jobs = state.get('display_jobs', {})
                if path == '/':
                    html = document(state)
                    links = '<h1>Print files and DSS_REPORTS spool</h1><ul>' + ''.join(
                        '<li><a href="/jobs/' + escape(key) + '">' + escape(
                            '%s: %s (%s, %s)' % (key, job['display'], job['format'], job['status']))
                        + '</a></li>' for key, job in jobs.items()) + '</ul>'
                    html = html.replace('</body>', links + '</body>').replace('<meta charset="utf-8">',
                        '<meta charset="utf-8"><meta http-equiv="refresh" content="2">')
                    body, kind = html.encode('utf-8'), 'text/html; charset=utf-8'
                elif re.fullmatch('/jobs/[1-9][0-9]*', path) and path.rsplit('/', 1)[1] in jobs:
                    job = jobs[path.rsplit('/', 1)[1]]
                    body, kind = job['content'].encode('ascii'), job['media_type']
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, sqlite3.Error):
                self.send_error(503, 'Display namespace is unavailable')

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--namespace')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    read = lambda: journal_state(args.journal, args.namespace)
    read()
    server = create_server(read, args.port)
    print('GCS displays: http://127.0.0.1:' + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
