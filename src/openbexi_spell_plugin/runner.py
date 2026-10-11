"""Standalone explicit-import SPELL development runner, usable from any IDE."""
from pathlib import Path
import runpy
import sys

from .runtime import activate


def main():
    if not sys.flags.isolated:
        raise RuntimeError('Run with an isolated interpreter (-I)')
    project, script = (Path(value).resolve() for value in sys.argv[1:3])
    if not project.is_dir() or not script.is_file() or not script.is_relative_to(project):
        raise ValueError('Invalid project/script boundary')
    activate()
    # Resolve the installed alias before adding mutable project imports.
    import spell.lang
    sys.path[:0] = list(dict.fromkeys([str(script.parent), str(project)]))
    sys.argv = [str(script), *sys.argv[3:]]
    runpy.run_path(str(script), run_name='__main__')


if __name__ == '__main__':
    main()
