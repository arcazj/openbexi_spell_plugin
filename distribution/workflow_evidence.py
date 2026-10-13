"""Local artifact/source checks shared by fresh workflow recorders; no Docker."""
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib
from importlib.machinery import all_suffixes
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
        lf_sha256=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest(), bytes=len(raw))


def exact_image(value):
    if not isinstance(value,str) or re.fullmatch('sha256:[0-9a-f]{64}',value) is None:
        raise ValueError('Expected an exact image SHA256')
    return value


def bound_file(binding, base):
    if not isinstance(binding,dict) or set(binding) != {'path','sha256'}:
        raise ValueError('Evidence input must name its exact path and SHA256')
    path = (Path(base)/binding['path']).resolve(strict=True)
    if sha(path) != binding['sha256']:
        raise ValueError('Evidence input SHA256 differs: '+str(path))
    return path


def source_inputs(inputs, root):
    if not inputs:
        raise ValueError('Source input map is empty')
    root = Path(root).resolve()
    for name, expected in inputs.items():
        path = (root/name).resolve(strict=True)
        if not path.is_relative_to(root) or sha(path) != expected:
            raise ValueError('Workflow source input differs: '+name)


def wheel(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute()
                or '..' in PurePosixPath(n).parts or '\\' in n or n.endswith('/') for n in names):
            raise ValueError('Unsafe or ambiguous wheel members')
        record, = [n for n in names if n.endswith('.dist-info/RECORD')]
        rows = list(csv.reader(io.StringIO(archive.read(record).decode('utf-8'))))
        if any(len(r)!=3 for r in rows) or len({r[0] for r in rows})!=len(rows) or {r[0] for r in rows}!=set(names):
            raise ValueError('Wheel RECORD member set differs')
        payload = {}
        for name,digest,size in rows:
            if name == record:
                if (digest,size)!=('',''):
                    raise ValueError('Wheel RECORD self-hash differs')
                continue
            raw = archive.read(name)
            actual = 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            if (actual,str(len(raw)))!=(digest,size):
                raise ValueError('Wheel RECORD bytes differ: '+name)
            payload[name]=raw
        info = BytesParser().parsebytes(payload[record.rsplit('/',1)[0]+'/METADATA'])
    return dict(name=info['Name'],version=info['Version'],sha256=sha(path),
        members={n:hashlib.sha256(raw).hexdigest() for n,raw in payload.items()}),payload


def installed_wheels(bindings, base):
    prefix = Path(sys.prefix).resolve()
    results = {}
    for name,binding in bindings.items():
        path = bound_file(binding,base)
        declared,payload = wheel(path)
        normalize = lambda value:re.sub('[-_.]+','-',value).lower()
        if normalize(declared['name']) != normalize(name):
            raise ValueError('Distribution name differs from selected wheel')
        package = metadata.distribution(name)
        if package.version != declared['version']:
            raise ValueError('Installed distribution version differs: '+name)
        for member,raw in payload.items():
            target = Path(package.locate_file(member)).resolve(strict=True)
            if not target.is_relative_to(prefix) or target.read_bytes()!=raw:
                raise ValueError('Installed payload differs: '+member)
        suffixes = tuple(set(all_suffixes())|{'.pyd','.so'})
        expected_sources = {n for n in payload if n.endswith(suffixes) and '.dist-info/' not in n}
        actual_sources = set()
        for top in {n.split('/')[0] for n in expected_sources}:
            target = Path(package.locate_file(top)).resolve(strict=True)
            if target.is_file():
                actual_sources.add(top)
            else:
                actual_sources.update(top+'/'+p.relative_to(target).as_posix() for p in target.rglob('*')
                    if p.is_file() and p.name.endswith(suffixes) and '__pycache__' not in p.relative_to(target).parts)
        if actual_sources != expected_sources:
            raise ValueError('Installed Python source set differs: '+name)
        results[name] = dict(**declared, installed_members_verified=len(payload))
    return results


def imported_modules(bindings, owners, base):
    results = {}
    for name,distribution in owners.items():
        selected = bound_file(bindings[distribution],base)
        declared,payload = wheel(selected)
        relative = name.replace('.','/')
        choices = [member for member in (relative+'/__init__.py',relative+'.py') if member in payload]
        if len(choices)!=1:
            raise ValueError('Expected one selected wheel member for executed module: '+name)
        member, = choices
        expected = Path(metadata.distribution(distribution).locate_file(member)).resolve(strict=True)
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve(strict=True)
        if origin != expected or Path(module.__spec__.origin).resolve(strict=True)!=expected:
            raise ValueError('Executed import differs from selected distribution member: '+name)
        if origin.read_bytes()!=payload[member] or not origin.is_relative_to(Path(sys.prefix).resolve()):
            raise ValueError('Executed import bytes/environment differ: '+name)
        results[name]=dict(distribution=distribution,member=member,origin=str(origin),
            sha256=sha(origin),wheel_sha256=declared['sha256'])
    return results


def wheel_source(path, source):
    result,payload = wheel(path)
    sources = {p.relative_to(source).as_posix():p.read_bytes() for p in Path(source).rglob('*.py') if '__pycache__' not in p.parts}
    actual = {name:raw for name,raw in payload.items() if name.endswith('.py') and '.dist-info/' not in name}
    if not sources or sources != actual:
        raise ValueError('Wheel Python source set/bytes differ: '+str(path))
    return result


def load(path):
    return json.loads(Path(path).read_bytes())
