"""Validate the project's ordered procedure-library folders."""
import json
from pathlib import Path, PurePosixPath


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate procedure-library field: '+key)
        result[key]=value
    return result


def priorities(project):
    path=Path(project)/'spell-library.json'
    if not path.exists():return ''
    if path.stat().st_size>16384:raise ValueError('Procedure-library configuration exceeds 16 KiB')
    config=json.loads(path.read_bytes(),object_pairs_hook=unique_object)
    if (type(config) is not dict or set(config)!={'schema','priorities'} or
            config['schema']!='openbexi.spell.library/1'):
        raise ValueError('Unsupported procedure-library configuration')
    folders=config['priorities']
    if type(folders) is not list or len(folders)>64:
        raise ValueError('Procedure-library priorities must be a list of at most 64 folders')
    seen=set()
    for folder in folders:
        if (type(folder) is not str or not folder or len(folder)>240 or
                any(ord(c)<32 or ord(c)==127 or c in '\\:' for c in folder) or
                PurePosixPath(folder).is_absolute() or any(p in ('','.','..') for p in folder.split('/'))):
            raise ValueError('Procedure-library priorities require relative folder paths')
        if folder in seen:raise ValueError('Duplicate procedure-library priority: '+folder)
        seen.add(folder)
    # Missing folders remain valid so one policy can cover several libraries.
    return '\x1f'.join(folders)
