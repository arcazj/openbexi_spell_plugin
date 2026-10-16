"""Bounded, read-only activation expressions over authoritative TM names."""
# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import operator

from .limit_definitions import number, text

ARITHMETIC = {ast.Add: operator.add, ast.Sub: operator.sub,
              ast.Mult: operator.mul, ast.Div: operator.truediv}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def reference(node):
    if isinstance(node, ast.Name):return node.id
    if isinstance(node, ast.Attribute):
        parent = reference(node.value)
        if parent:return parent+'.'+node.attr
    return None


class Algorithm:
    def __init__(self, expression, lookup):
        text(expression, 1024, 'activation algorithm')
        self.references = set()
        self.root = None
        if not expression:return
        try:self.root = ast.parse(expression, mode='eval').body
        except (SyntaxError, RecursionError) as error:
            raise ValueError('Invalid activation expression') from error
        if sum(1 for _ in ast.walk(self.root)) > 128:
            raise ValueError('Activation expression is too complex')
        self._validate(self.root, lookup, 0)

    def _validate(self, node, lookup, depth):
        if depth > 16:raise ValueError('Activation expression nesting exceeds bounds')
        name = reference(node)
        if name:
            lookup(name)
            self.references.add(name)
            return
        if isinstance(node, ast.Constant):
            if type(node.value) is str:text(node.value, 256, 'activation string')
            elif type(node.value) is not bool:number(node.value)
            return
        children = None
        if isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC:
            children = [node.left, node.right]
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.Not, ast.UAdd, ast.USub):
            children = [node.operand]
        elif isinstance(node, ast.BoolOp) and type(node.op) in (ast.And, ast.Or):
            children = node.values
        elif isinstance(node, ast.Compare) and all(type(op) in COMPARE for op in node.ops):
            children = [node.left, *node.comparators]
        if children is None:raise ValueError('Unsupported activation expression operation')
        for child in children:self._validate(child, lookup, depth+1)

    def evaluate(self, acquire):
        if self.root is None:return True
        values = {}
        def evaluate(node):
            name = reference(node)
            if name:
                if name not in values:values[name] = acquire(name)
                return values[name]
            if isinstance(node, ast.Constant):return node.value
            if isinstance(node, ast.BinOp):
                left, right = number(evaluate(node.left)), number(evaluate(node.right))
                return number(ARITHMETIC[type(node.op)](left, right))
            if isinstance(node, ast.UnaryOp):
                value = evaluate(node.operand)
                if isinstance(node.op, ast.Not):
                    if type(value) is not bool:raise ValueError('Activation Boolean required')
                    return not value
                return number(number(value) if isinstance(node.op, ast.UAdd) else -number(value))
            if isinstance(node, ast.BoolOp):
                for child in node.values:
                    value = evaluate(child)
                    if type(value) is not bool:raise ValueError('Activation Boolean required')
                    if isinstance(node.op, ast.And) and not value:return False
                    if isinstance(node.op, ast.Or) and value:return True
                return isinstance(node.op, ast.And)
            left = evaluate(node.left)
            for op, child in zip(node.ops, node.comparators):
                right = evaluate(child)
                if not COMPARE[type(op)](left, right):return False
                left = right
            return True
        try:value = evaluate(self.root)
        except (ArithmeticError, TypeError) as error:
            raise ValueError('Activation expression cannot be evaluated') from error
        if type(value) is not bool:raise ValueError('Activation expression must return Boolean')
        return value
