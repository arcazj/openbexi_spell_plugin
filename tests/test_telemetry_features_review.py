"""Packet and native-output evidence must survive an independent review."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
import telemetry_features_review as report

RAW = Path('C:/obtelemetry_review/.qualification/telemetry-features/ec2c8b03d66c42f0a4e37ee624efaa9f/result.json')
RAW_SHA = '7c65d034e2cfc2577a9a7c30b2bf33efbbb549dc4d557d7cd641db59a6b9d531'
REVISION = '0cb3884877525a07aa26306d069c50db925e3ebe'
OVERLAY = Path('C:/oblimit_impl/.qualification/telemetry-review-preflight/0456518e9e684feb92be3acbe7c81ed8/overlay')
LIMIT_OVERLAY = Path('C:/oblimit_review/.qualification/limit-review-preflight/28afbc466d9c465c8eaac5b66ad6f6e4/overlay')


@pytest.fixture(scope='module')
def retained():
    assert report.sha(RAW) == RAW_SHA
    raw = report.read(RAW)
    assert {name for name,row in raw['checks'].items() if not row['passed']} == {'between-list:boundary'}
    cases = report.frozen('conformance/telemetry_features_cases.py', REVISION).CASES
    return raw, cases


def test_all_thirty_one_successful_cases_have_independent_packet_and_output_proofs(retained):
    raw, cases = retained
    reviewed = [report.case_proof(name,cases[name],row,RAW.parent/'workspace'/name.replace(':','__'))
                for name,row in raw['checks'].items() if row['passed']]
    assert len(reviewed) == 31 and all(row['passed'] for row in reviewed)
    report.provenance(raw,OVERLAY,LIMIT_OVERLAY,REVISION)


def test_partial_native_run_cannot_be_accepted_as_complete(retained):
    raw, _ = retained
    with pytest.raises(ValueError, match='Raw report failed: between-list:boundary'):
        report.review(RAW,OVERLAY,LIMIT_OVERLAY,REVISION,raw['runtime_image'])


@pytest.mark.parametrize('mutation', ['packet-value', 'printed-result', 'early-deadline', 'procedure-source'])
def test_rebound_record_cannot_hide_wrong_packet_output_or_elapsed_time(tmp_path,retained,mutation):
    raw,cases = retained
    name = {'packet-value':'quality:positive', 'printed-result':'printed:positive',
            'early-deadline':'minute:positive', 'procedure-source':'quality:positive'}[mutation]
    row = deepcopy(raw['checks'][name])
    project = tmp_path/name.replace(':','__')
    shutil.copytree(RAW.parent/'workspace'/project.name, project)
    if mutation == 'packet-value':
        call = next(call for call in row['rpc'] if call['path'].endswith('/RefreshItem'))
        shape = report.p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TM'].methods_by_name['RefreshItem'].output_type
        answer = report.GetMessageClass(shape).FromString(bytes.fromhex(call['response']))
        from openbexi_spell_dss.codec import pack
        answer.engValue.CopyFrom(pack(99.0))
        call['response'] = answer.SerializeToString().hex()
    elif mutation == 'printed-result':
        events = report.read(project/'events.json')
        event = next(item for item in events if item.get('message',{}).get('fields',{}).get('Text') == '0: TM.POWER.BUS_VOLTAGE : True')
        event['message']['fields']['Text'] = '0: TM.POWER.BUS_VOLTAGE : False'
        (project/'events.json').write_text(json.dumps(events),encoding='utf-8')
        row['events_sha256'] = report.sha(project/'events.json')
    elif mutation == 'early-deadline':
        call = next(call for call in row['rpc'] if call['path'].endswith('/RefreshItem'))
        call['elapsed'] = 1.0
        item = next(item for item in row['observed']['observations'] if 'acquisition_elapsed' in item)
        item['acquisition_elapsed'] = 1.0
        (project/'observed.json').write_text(json.dumps(row['observed']),encoding='utf-8')
    else:
        row['source'] = 'pass\n'
        (project/'main.py').write_text(row['source'],encoding='utf-8')
    with pytest.raises(AssertionError):
        report.case_proof(name,cases[name],row,project)
