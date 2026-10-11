"""Separate processes for crash and continuation qualification.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import json
import os
from pathlib import Path
import signal
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persistent_codec import load, probe, save

mode, source_file, checkpoint, result_file, line, occurrence, subject_name = sys.argv[1:]
source = Path(source_file).read_bytes()
if mode == 'capture':
    program = compile(source, source_file, 'exec')
    subject = program if subject_name == '<module>' else next(
        c for c in program.co_consts if isinstance(c, types.CodeType) and c.co_name == subject_name)
    def persist(state):
        save(checkpoint, source, state)
        # No Python exception/finally unwinding is allowed to stand in for a crash.
        os.kill(os.getpid(), signal.SIGKILL)
    probe.capture(program, subject, {}, int(line), int(occurrence), persist)
    raise RuntimeError('Capture unexpectedly returned')
elif mode == 'resume':
    result, namespace, offset, slots = probe.resume(load(checkpoint, source))
    Path(result_file).write_text(json.dumps({'return':result, 'result':namespace.get('result'),
        'offset':offset, 'slots':slots}))
else:
    raise ValueError(mode)
