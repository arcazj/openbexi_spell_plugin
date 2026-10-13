"""One exposed native prompt, with answers bound to its actual procedure."""
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass


@dataclass(eq=False)
class Prompt:
    identifier: str
    procedure: str
    fields: dict
    phase: str = 'queued'


class PromptQueue:
    def __init__(self, root):
        self.root = root
        self.pending = []
        self.active = None
        self.answering = None
        self.sequence = 0
        self.failure = None

    def invalidate(self, procedure):
        self.pending[:] = [entry for entry in self.pending if entry.procedure != procedure]
        if self.active and self.active.procedure == procedure:
            self.active = None

    def observe(self, message, children=()):
        fields = message.get('fields', {})
        procedure = fields.get('ProcId')
        if not procedure:
            return
        if (message.get('id') == 'MSG_EXEC_OP' and fields.get('ExecOp') in {'CLOSE', 'KILL'}
                or fields.get('DataType') == 'STATUS' and fields.get('ExecutorStatus')
                and fields['ExecutorStatus'] != 'PROMPT'):
            self.invalidate(procedure)
            return
        if message.get('id') != 'MSG_PROMPT' or procedure != self.root and procedure not in children:
            return
        for entry in self.pending + ([self.active] if self.active else []):
            if entry.procedure == procedure:
                if entry.fields == fields:
                    return  # repeated delivery cannot publish another answer opportunity
                if entry is self.active and entry.phase == 'sending':
                    continue  # next prompt can arrive before the send reply
                raise RuntimeError('Multiple pending native prompts for ' + procedure)
        if len(self.pending) + bool(self.active) >= 128:
            raise RuntimeError('Native prompt queue exceeds 128 procedures')
        self.sequence += 1
        self.pending.append(Prompt(str(self.sequence), procedure, dict(fields)))

    def expose(self, repeat=False):
        if self.failure:
            raise RuntimeError(self.failure)
        if self.answering:
            return None
        if self.active:
            return self.active if repeat else None
        if not self.pending:
            return None
        self.active = self.pending.pop(0)
        self.active.phase = 'active'
        return self.active

    def begin(self, identifier=None):
        if self.failure:
            raise RuntimeError(self.failure)
        if self.answering or self.active is None:
            raise ValueError('No active native prompt accepts an answer')
        if identifier is not None and identifier != self.active.identifier:
            raise ValueError('Stale or unknown native promptId')
        self.answering = self.active
        self.active.phase = 'checking'
        return self.active

    def before_send(self, entry):
        if self.active is not entry or self.answering is not entry:
            raise ValueError('The native prompt closed before its answer was sent')
        entry.phase = 'sending'

    def complete(self, entry):
        if self.active is entry:
            self.active = None
        self.answering = None

    def cancel(self, entry):
        if entry.phase == 'sending':
            # A transport failure cannot establish whether the executor consumed
            # the answer. Fail the session rather than replay or advance prompts.
            self.failure = 'Native prompt answer outcome is uncertain; session must close'
        else:
            entry.phase = 'active'
        self.answering = None
