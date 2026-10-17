"""Recheck native messages and the immutable durable event journal independently."""
from collections import Counter
import hashlib,json,re
from pathlib import Path
from aggregate_support import ROOT,sha,read,ref
from evidence_database import evidence_database
from events_report import qualify as qualify_existing
from installed_provenance import verify_capture
from limit_telemetry_sources import wheel_sources, verify_driver_capture
from run_language_regressions import validate_report


def expected_events():
    return [('',8,1),('EV:info',8,1),('EV:warning',1,1),('EV:error',2,1),
        ('EV:boundary:'+('caf\u00e9\n'*3277),1,1),('',8,1),('EV:recovery',8,1)]


def review(path,image,native_wheel,driver_wheel):
    validate_report(path,image,8);raw=read(path)
    report=qualify_existing(raw);workspace=path.parent/'workspace'
    assert read(workspace/'observations.json')==raw['observations']
    assert read(workspace/'runtime.json')==raw['runtime_sources']
    assert read(workspace/'procedure/cases.json')=={key:row['source'] for key,row in raw['checks'].items()}
    for filename,relative in (('controller.py','events_controller.py'),
        ('procedure/events_contracts.py','events_contracts.py'),('procedure/cmd_contracts.py','cmd_contracts.py')):
        assert sha(workspace/filename)==raw['inputs']['conformance/'+relative]
    runtime=raw['runtime_sources'];captured=runtime['integrated']
    verify_capture(captured,raw['inputs'],raw.get('lf_normalized_inputs'))
    native=wheel_sources(native_wheel);driver=wheel_sources(driver_wheel)
    assert captured['manifest']==json.loads(native['spell_native/manifest.json'])
    assert captured['manifest_sha256']==hashlib.sha256(native['spell_native/manifest.json']).hexdigest()
    recipes=captured['manifest']['composition']['native']['recipes']
    assert 'event_text_patches.py' in recipes
    verify_driver_capture(driver,recipes,captured['driver_composition'])
    for name,value in {**native,**driver}.items():
        installed='/usr/local/lib/python3.13/site-packages/'+name
        if installed in runtime['installed']:assert runtime['installed'][installed]==hashlib.sha256(value).hexdigest()
    with evidence_database(workspace/'driver.sqlite') as db:
        journal=db.execute('SELECT message,severity,scope FROM events ORDER BY created_ns').fetchall()
    # Original executor lifecycle events bracket the explicitly injected events.
    assert len(journal)==len(expected_events())+2
    assert journal[0][1:]==journal[-1][1:]==(8,1)
    assert re.fullmatch(r'Procedure started: main#1 at \d{4}-\d\d-\d\d \d\d:\d\d:\d\d',journal[0][0])
    assert re.fullmatch(r'Procedure finished: main#1 at \d{4}-\d\d-\d\d \d\d:\d\d:\d\d \(status FINISHED\)',journal[-1][0])
    assert journal[1:-1]==expected_events()
    messages=[event['message']['fields'] for event in raw['observations']['events']
        if event.get('message',{}).get('id')=='MSG_WRITE']
    selected=[m for m in messages if m.get('Text')=='' or m.get('Text','').startswith('EV:')
        or m.get('Text') in ('INVALID_SEVERITY','INVALID_SCOPE')]
    actual=Counter((m['Text'],m['Level'],m['Scope']) for m in selected)
    levels={8:'INFO',1:'WARN',2:'ERROR'}
    assert actual==Counter((text,levels[severity],str(scope)) for text,severity,scope in expected_events())
    report.update(passed=True,raw=ref(path),composed_wheels=dict(passed=True,
        native_wheel=ref(native_wheel),driver_wheel=ref(driver_wheel),complete_records_verified=True),
        event_journal=ref(workspace/'driver.sqlite'),native_events=ref(workspace/'observations.json'))
    report['inputs']['conformance/event_text_review.py']=sha(ROOT/'conformance/event_text_review.py')
    report['scope']['event']='Empty, Unicode/newline and messages over 16,384 characters reach the original native client and durable event journal exactly once; invalid argument types, severity and scope have no event effect; subsequent calls recover.'
    report['scope'].pop('event_open', None)
    return report
