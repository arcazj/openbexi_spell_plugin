"""Conservative CPython 3.13 stack analysis for literal native Step labels.

SPDX-License-Identifier: GPL-3.0-or-later
The first argument must originate from LOAD_CONST. The second can be arbitrary.
No procedure expression is evaluated while identifying its jump destinations.
"""
import dis
from collections import deque


def analyze_flow(code):
    instructions = list(dis.get_instructions(code))
    if not instructions:
        return []
    offsets = {instruction.offset: index for index, instruction in enumerate(instructions)}
    states, pending = {}, deque()

    def merge(index, state):
        if index >= len(instructions):
            return
        old = states.get(index)
        state = tuple(state)
        if old is None:
            states[index] = state
            pending.append(index)
        elif len(old) == len(state):
            combined = tuple(left if left == right else None for left, right in zip(old, state))
            if combined != old:
                states[index] = combined
                pending.append(index)
        # Valid compiled Python has consistent operand-stack depth at a merge.
        # An inconsistent state must not manufacture a label.
        else:
            combined = (None,) * max(len(old), len(state))
            if combined != old:
                states[index] = combined
                pending.append(index)

    merge(0, ())
    for entry in dis.Bytecode(code).exception_entries:
        merge(offsets[entry.target], (None,) * (entry.depth + 1 + entry.lasti))
    while pending:
        index = pending.popleft()
        instruction = instructions[index]
        operation, argument = instruction.opname, instruction.arg
        original = list(states[index])
        is_jump = instruction.opcode in dis.hasjump
        successors = []
        if is_jump:
            successors.append((offsets[instruction.argval], True))
        if operation not in ('RETURN_VALUE', 'RETURN_CONST', 'RAISE_VARARGS', 'RERAISE') and not operation.startswith('JUMP_'):
            successors.append((index + 1, False))
        for successor, jump in successors:
            stack = original[:]
            effect = dis.stack_effect(instruction.opcode, argument, jump=jump)
            if operation in ('LOAD_NAME', 'LOAD_GLOBAL'):
                value = ('callable', instruction.argval) if instruction.argval in ('Step', 'Goto') else None
                stack.append(value)
                if effect == 2:
                    stack.append(('null', ''))
            elif operation == 'LOAD_CONST':
                stack.append(('literal', instruction.argval) if type(instruction.argval) is str else None)
            elif operation == 'PUSH_NULL':
                stack.append(('null', ''))
            elif operation == 'COPY':
                stack.append(stack[-argument] if len(stack) >= argument else None)
            elif operation == 'SWAP' and len(stack) >= argument:
                stack[-1], stack[-argument] = stack[-argument], stack[-1]
            elif operation in ('CALL', 'CALL_KW'):
                consumed = argument + (3 if operation == 'CALL_KW' else 2)
                stack = stack[:-consumed] if len(stack) >= consumed else []
                stack.append(None)
            elif operation.startswith(('STORE_', 'DELETE_', 'POP_JUMP')) or operation in (
                    'POP_TOP', 'JUMP_FORWARD', 'JUMP_BACKWARD', 'JUMP_BACKWARD_NO_INTERRUPT'):
                if effect < 0:
                    stack = stack[:effect]
                elif effect > 0:
                    stack.extend([None] * effect)
            else:
                if effect < 0:
                    stack = stack[:effect]
                    if stack:
                        stack[-1] = None
                elif effect > 0:
                    stack.extend([None] * effect)
                elif stack and operation not in ('RESUME', 'NOP', 'EXTENDED_ARG'):
                    stack[-1] = None
            merge(successor, stack)
    found = []
    for index, state in states.items():
        instruction = instructions[index]
        if instruction.opname != 'CALL':
            continue
        arity = instruction.arg
        if len(state) < arity + 2:
            continue
        function = state[-arity - 2]
        if function not in (('callable', 'Step'), ('callable', 'Goto')):
            continue
        kind = function[1]
        if arity != (2 if kind == 'Step' else 1):
            continue
        label = state[-arity]
        if label is None or label[0] != 'literal':
            continue
        title = state[-1] if kind == 'Step' else None
        title = title[1] if title is not None and title[0] == 'literal' else None
        found.append((kind, label[1], title, instruction.offset))
    return sorted(set(found), key=lambda row: row[3])
