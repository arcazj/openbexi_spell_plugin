"""Client-side startup for original SPELL visible child procedures.

The native executor deliberately leaves visible automatic children paused until
their controlling GUI sends RUN. Observe notifications without issuing nested
RPCs: Bridge.exchange pumps these notifications while another reply is pending.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import re


class ChildProcedures:
    def __init__(self, root, present=None, *, admit_hidden=False):
        self.root = root
        self.children = {}
        self.present = present
        self.admit_hidden = admit_hidden

    def observe(self, message):
        fields = message.get('fields', {})
        procedure = fields.get('ProcId')
        if message.get('id') != 'MSG_EXEC_OP' or not procedure:
            return
        operation = fields.get('ExecOp')
        if operation == 'OPEN':
            parent = fields.get('ParentId')
            if procedure != self.root and (parent == self.root or parent in self.children):
                self.children.setdefault(procedure, {'parent': parent, 'pending': True})
        elif operation in {'CLOSE', 'KILL'}:
            self.children.pop(procedure, None)

    def service(self, session):
        # A reply can pump new child notifications and mutate this inventory.
        for procedure, child in list(self.children.items()):
            if not child['pending']:
                continue
            info = session.request('REQ_EXEC_INFO', context=True, procedure=procedure)
            if self.children.get(procedure) is not child:
                continue
            mode = info.get('OpenMode', '')
            match = re.fullmatch(
                r'\{Automatic:(True|False),Visible:(True|False),Blocking:(True|False)\}', mode)
            if not match:
                raise RuntimeError('Invalid native child open mode: ' + mode)
            if match.group(2) == 'True' and self.present and not child.get('presented'):
                # Present only owned, visible procedures, once per OPEN lifetime.
                # Do this before the initial RUN; repeated status polls must not
                # reprint source, and hidden procedures must not read it at all.
                child['presented'] = True
                self.present(procedure)
            if match.group(1) != 'True' or (match.group(2) != 'True' and not self.admit_hidden):
                child['pending'] = False
                continue
            status = info.get('ExecutorStatus')
            if status == 'PAUSED':
                # Mark before sending: never replay a RUN after a breakpoint,
                # repeated PAUSED notification, or an uncertain send outcome.
                child['pending'] = False
                session.request('CMD_RUN', send=True, procedure=procedure)
            elif status in {'RUNNING', 'PROMPT', 'WAITING', 'FINISHED', 'ERROR', 'ABORTED'}:
                child['pending'] = False
