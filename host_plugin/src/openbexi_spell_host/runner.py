"""Execute explicit-import SPELL procedures using the native DAP runtime."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

from .container import Container
from .protocol import read, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--program', required=True)
    parser.add_argument('--image')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    project, program = Path(args.project).resolve(), Path(args.program).resolve()
    if not program.is_file() or not program.is_relative_to(project):
        parser.error('Program must be an existing file inside the selected project')
    container = Container(project, args.image)
    messages = queue.Queue(maxsize=256)
    stopped = threading.Event()
    process = None
    reader = None
    sequence = 0
    exit_code = 1
    eof = False
    prompt = False
    disconnecting = False

    def publish(value):
        while not stopped.is_set():
            try:
                messages.put(value, timeout=.1)
                return
            except queue.Full:
                continue

    def read_adapter():
        try:
            while (message := read(process.stdout)) is not None:
                publish(message)
            publish(None)
        except Exception as error:
            publish(error)

    def read_input():
        # Raw OS reads avoid a daemon holding Python's buffered stdin lock at
        # finalization when a desktop console remains open after completion.
        pending = bytearray()
        while not stopped.is_set():
            data = os.read(sys.stdin.fileno(), 8192)
            if not data:
                publish({'inputEof': True})
                return
            pending.extend(data)
            if len(pending) > 65536:
                publish(ValueError('Prompt input exceeds 64 KiB'))
                return
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                publish({'input': line.decode('utf-8').rstrip('\r')})

    def send(command, **values):
        nonlocal sequence
        sequence += 1
        write(process.stdin, {'seq': sequence, 'type': 'request', 'command': command, 'arguments': values})

    try:
        process = container.start(stderr=sys.stderr.buffer)
        reader = threading.Thread(target=read_adapter)
        reader.start()
        threading.Thread(target=read_input, daemon=True).start()
        send('initialize', adapterID='spell', linesStartAt1=True, pathFormat='path')
        while True:
            try:
                message = messages.get(timeout=40 if not disconnecting else 15)
            except queue.Empty:
                if process.poll() is not None:
                    break
                if disconnecting:
                    raise RuntimeError('Native shutdown timed out')
                continue
            if message is None:
                break
            if isinstance(message, Exception):
                raise message
            if message.get('inputEof'):
                eof = True
                if os.environ.get('OPENBEXI_HOST_MANAGED') == '1' or prompt:
                    exit_code = 130
                    send('disconnect', terminateDebuggee=True)
                    disconnecting = True
            elif 'input' in message:
                if prompt:
                    send('spell/promptAnswer', value=message['input'])
                    prompt = False
            elif message.get('type') == 'response':
                if not message.get('success'):
                    raise RuntimeError(message.get('message', 'Native command failed'))
                if message['command'] == 'initialize' and not disconnecting:
                    send('launch', project=str(project), program=str(program), args=arguments, noDebug=True)
            elif message.get('event') == 'initialized' and not disconnecting:
                send('configurationDone')
            elif message.get('event') == 'output':
                body = message['body']
                stream = sys.stderr if body.get('category') == 'stderr' else sys.stdout
                print(body.get('output', ''), end='', file=stream, flush=True)
            elif message.get('event') == 'spell/prompt':
                prompt = True
                values = message['body'].get('ExpectedValues', '')
                print('SPELL choices (enter the native option index): ' + values, flush=True)
                if eof:
                    raise RuntimeError('SPELL prompt requires input but stdin is closed')
            elif message.get('event') == 'exited':
                exit_code = message['body']['exitCode']
            elif message.get('event') == 'terminated':
                destination = container.export()
                print('SPELL run files: ' + str(destination), file=sys.stderr, flush=True)
                send('disconnect', terminateDebuggee=True)
                disconnecting = True
        return exit_code
    except KeyboardInterrupt:
        exit_code = 130
        return exit_code
    except Exception as error:
        print('SPELL host: ' + str(error), file=sys.stderr, flush=True)
        return 1
    finally:
        stopped.set()
        if process and process.poll() is None:
            try:
                send('disconnect', terminateDebuggee=True)
            except OSError:
                pass
        if process:
            try:
                process.stdin.close()
            except OSError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        container.close()
        if reader:
            reader.join(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
