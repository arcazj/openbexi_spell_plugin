"""Rebuild retained prompt observers from the exact historical generator."""
import ast
from pathlib import PurePosixPath


def generated_sources(root,revision,suite):
    from evidence_sources import source_bytes
    source=source_bytes(root,'conformance/run_prompt_startup.py',revision)
    function,=[node for node in ast.parse(source).body
               if isinstance(node,ast.FunctionDef) and node.name=='sources_for']
    assert [arg.arg for arg in function.args.args]==['suite']

    class CommittedPath:
        def __init__(self,name=''):self.name=PurePosixPath(name)
        def __truediv__(self,name):return CommittedPath(self.name/name)
        def read_bytes(self):return source_bytes(root,self.name.as_posix(),revision)

    namespace={'ROOT':CommittedPath()}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'retained prompt generator','exec'),namespace)
    return namespace['sources_for'](suite)


def cases(root,revision,name):
    from evidence_sources import source_bytes
    namespace={}
    exec(compile(source_bytes(root,'conformance/'+name,revision),name,'exec'),namespace)
    return namespace['CASES']
