"""DAP relay for IDE hosts; private native execution and preserved output files."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import sys

from .local import runtime
from .protocol import read, write
from .sound import reminder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--image')
    args = parser.parse_args()
    container = runtime(args.project, args.image)
    try:
        process = container.start(stdin=sys.stdin.buffer, stderr=sys.stderr.buffer)
        while (message := read(process.stdout)) is not None:
            if message.get('event') == 'openbexi/promptReminder':
                reminder()
            if message.get('event') == 'terminated':
                destination = container.export()
                if destination:
                    print('SPELL run files: ' + str(destination), file=sys.stderr, flush=True)
            write(sys.stdout.buffer, message)
        return process.wait(timeout=10)
    except Exception as error:
        print('SPELL host: ' + str(error), file=sys.stderr, flush=True)
        return 1
    finally:
        container.close()


if __name__ == '__main__':
    raise SystemExit(main())
