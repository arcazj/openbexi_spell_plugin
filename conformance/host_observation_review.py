"""Recheck retained host artifacts against immutable wheel RECORDs and source bytes."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report
from installed_provenance import verify_capture
from limit_telemetry_sources import wheel_sources, verify_driver_capture

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def evidence(path,image,count,native_wheel,driver_wheel):
    validate_report(path,image,count)
    raw=read(path);assert raw['passed'] is True and len(raw['checks'])==count
    native=wheel_sources(native_wheel);driver=wheel_sources(driver_wheel)
    manifest=json.loads(native['spell_native/manifest.json'])
    recipes=manifest['composition']['native']['recipes']
    expected_host={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    captured=None
    for name,row in raw['checks'].items():
        directory=path.parent/name.replace(':','-')
        assert row['passed'] is True and not any(k.endswith('_error') for k in row)
        assert row['artifacts']=={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
        assert row['runtime']==read(directory/'runtime.json')
        runtime=row['runtime'];assert runtime['host']==expected_host
        integrated=runtime['integrated'];verify_capture(integrated,raw['inputs'])
        assert integrated['manifest']==manifest
        assert integrated['manifest_sha256']==hashlib.sha256(native['spell_native/manifest.json']).hexdigest()
        verify_driver_capture(driver,recipes,integrated['driver_composition'])
        if captured is not None:assert integrated==captured
        captured=integrated
        transcript=read(directory/'transcript.json')
        exits=[m['body'] for m in transcript if m.get('event')=='exited']
        assert exits==[{'exitCode':0}]==[row['exit']]
        assert sum(m.get('event')=='terminated' for m in transcript)==1
        assert not any(m.get('event')=='output' and m.get('body',{}).get('category')=='stderr'
            and any(s in m['body'].get('output','') for s in ('AddressSanitizer:','runtime error:'))
            for m in transcript)
    return raw,dict(passed=True,native_wheel=ref(native_wheel),driver_wheel=ref(driver_wheel),
        complete_records_verified=True,host_sources=expected_host)
