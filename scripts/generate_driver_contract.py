"""Extract and generate the exact original driver contract, with provenance."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'driver_plugin/src/openbexi_spell_dss'
ARCHIVE_SHA256 = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'


def main():
    import grpc_tools
    from importlib.metadata import version
    archive = ROOT / 'docs/reference/SPELL2.6.10-src.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Original source archive identity differs')
    if version('grpcio-tools') != '1.84.0':
        raise ValueError('Use the pinned grpcio-tools 1.84.0 generator')
    with zipfile.ZipFile(archive) as source:
        names = [name for name in source.namelist() if name.endswith('/protos/SPELLDriver.proto') or name == 'protos/SPELLDriver.proto']
        if len(names) != 1:
            raise ValueError('Ambiguous original driver protocol')
        raw = source.read(names[0])
    contracts = DEST / 'contracts'
    contracts.mkdir(parents=True, exist_ok=True)
    schema = contracts / 'SPELLDriver.proto'
    schema.write_bytes(raw)
    subprocess.run([sys.executable, '-m', 'grpc_tools.protoc', '-I' + str(contracts),
        '-I' + str(Path(grpc_tools.__file__).parent / '_proto'),
        '--python_out=' + str(DEST / 'stubs'), '--grpc_python_out=' + str(DEST / 'stubs'), str(schema)], check=True)
    stub = DEST / 'stubs/SPELLDriver_pb2_grpc.py'
    text = stub.read_text()
    old = 'import SPELLDriver_pb2 as SPELLDriver__pb2'
    if text.count(old) != 1:
        raise ValueError('Generated import shape differs')
    stub.write_text(text.replace(old, 'from . import SPELLDriver_pb2 as SPELLDriver__pb2'), newline='\n')
    provenance = {'archive_sha256': ARCHIVE_SHA256, 'archive_member': names[0],
        'schema_sha256': hashlib.sha256(raw).hexdigest(), 'generator': 'grpcio-tools==1.84.0',
        'patch': 'Package-relative generated Python import only; protocol bytes unchanged',
        'generated_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((DEST / 'stubs').glob('SPELLDriver*.py'))}}
    (contracts / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    main()
