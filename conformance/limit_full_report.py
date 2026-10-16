"""Require complete composed native evidence for the remaining 52 LIMIT rows."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'distribution'),str(ROOT/'driver_plugin/src')]
from limit_features_review import review, frozen
from limit_report import read_passed, GROUPS as LEGACY_GROUPS
from run_language_regressions import SUITES

PREFIX='CMP-LRM244-'
DIMENSIONS=('positive','boundary','failure','recovery')
MAP={}


def bind(rows,*features):
    for row in rows:
        assert row not in MAP
        MAP[row]=features


bind(['CONSTANT-LIMIT-SELECTION-ACTIVE','MODIFIER-ACTIVE','MODIFIER-SELECT',
      'EXAMPLE-088','EXAMPLE-089','SECTION-4-8-1-072'],'named','activation','selectors')
bind(['EXAMPLE-085','EXAMPLE-086'],'named','metadata','selectors')
bind(['EXAMPLE-087','EXAMPLE-090'],'status','properties','metadata')
bind(['EXAMPLE-091'],'properties')
bind(['EXAMPLE-092'],'named','paired-properties')
bind(['EXAMPLE-093'],'paired-properties','spike','step')
bind(['EXAMPLE-094','EXAMPLE-095'],'round-trip','named')
bind(['EXAMPLE-097'],'round-trip','status')
bind(['EXAMPLE-098'],'properties','status')
bind(['CONSTANT-LIMIT-TYPE-STATUS','MODIFIER-NOMINAL','MODIFIER-WARNING'],'status','properties','adjust-status')
bind(['CONSTANT-LIMIT-TYPE-SPIKE','EXAMPLE-100'],'spike','selectors')
bind(['CONSTANT-LIMIT-TYPE-STEP','EXAMPLE-101'],'step','selectors')
bind(['MODIFIER-DELTA'],'spike','step','paired-properties')
bind(['MODIFIER-HIBOTH','MODIFIER-LOBOTH'],'paired-properties')
bind(['MODIFIER-HYSTERESIS'],'hysteresis','metadata')
bind(['MODIFIER-ALGORITHM'],'activation','metadata')
bind(['FUNCTION-ENABLEALARM','FUNCTION-DISABLEALARM','EXAMPLE-102','SECTION-4-8-6-077'],
     'alarm-control','hysteresis')
bind(['EXAMPLE-103'],'adjust-analog','adjust-filter')
bind(['EXAMPLE-104'],'adjust-status','adjust-filter')
bind(['FUNCTION-CANDIDATE-ADJUSTLIMITS','SECTION-4-8-7-078','ERRATUM-ADJUSTLIMITS-NAME'],
     'adjust-analog','adjust-status','adjust-filter')
bind(['EXAMPLE-105','FUNCTION-LOADLIMITS','SECTION-4-8-8-079','SYNTAX-URI-LIMITS'],'limit-file')
bind(['ERRATUM-LIMIT-KEY-LOHIGH'],'properties','paired-properties')
TYPES=('metadata','status','spike','step','hysteresis','activation','paired-properties')
READ=('named','selectors','properties','round-trip',*TYPES)
WRITE=(*READ,'adjust-analog','adjust-status','adjust-filter')
bind(['SECTION-4-8-2-073','SECTION-4-8-3-074'],*TYPES)
bind(['FUNCTION-GETLIMITS','SECTION-4-8-4-075'],*READ)
bind(['FUNCTION-SETLIMITS','SECTION-4-8-5-076','MODIFIER-LIMITS','TYPE-LIMITDEFINITION'],*WRITE)
bind(['SECTION-4-8-071'],*WRITE,'alarm-control','limit-file')

read=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def verify_mapping():
    inventory={row['id'] for row in read(ROOT/'conformance/inventory.json')['rows'] if row['package']=='LIMIT'}
    previous={PREFIX+row for group in LEGACY_GROUPS.values() for row in group['contracts']}
    assert len(MAP)==52 and {PREFIX+row for row in MAP}==inventory-previous
    from limit_features_cases import CASES
    assert len(CASES)==64
    for features in MAP.values():
        assert features and len(features)==len(set(features))
        assert all(feature+':'+dimension in CASES for feature in features for dimension in DIMENSIONS)


def qualify(path,legacy_path,sequence_path,revision,image,native_wheel,driver_wheel):
    verify_mapping()
    sequence=read(sequence_path)
    assert sequence['passed'] and sequence['state']=='completed' and sequence['complete_sequence']
    assert sequence['image']==image and sequence['source_commit']==revision
    assert [(row['suite'],row['passed']) for row in sequence['suites']]==[(name,True) for name,*_ in SUITES]
    stages={row['suite']:row['raw'] for row in sequence['suites']}
    assert stages['limit-features']['path']==str(path) and stages['limit-features']['sha256']==sha(path)
    assert stages['limit']['path']==str(legacy_path) and stages['limit']['sha256']==sha(legacy_path)
    legacy=read_passed(legacy_path,'limit')
    assert legacy['runtime_image']==image and len(legacy['checks'])==79
    cases=frozen('conformance/limit_features_cases.py',revision).CASES
    reviewed=review(path,None,revision,image,list(cases),native_wheel,driver_wheel)
    assert reviewed['composed_wheels']['passed']
    checks=deepcopy(reviewed['checks'])
    for key,row in checks.items():
        row['contracts']=[]
    for identifier,features in MAP.items():
        for dimension in DIMENSIONS:
            dependencies=[feature+':'+dimension for feature in features]
            assert all(checks[key]['passed'] and checks[key]['dimension']==dimension for key in dependencies)
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,legacy_spelling_supported=True,
                oracle='LRM pp59-67 and appendix modifiers: explicit original native calls, literal value/exception oracles, actual OOL transitions and durable original-schema effects agree; complete prior LIMIT behavior also passed on this same composed image.')
    return dict(passed=True,runtime_image=image,source_revision=revision,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),native_checks=64,legacy_native_checks=79,
        feature_review=reviewed,raw=ref(path),legacy_raw=ref(legacy_path),sequence=ref(sequence_path),
        inputs={**reviewed['source_inputs'],**{name:sha(ROOT/name) for name in
            ('conformance/limit_full_report.py','conformance/limit_features_review.py',
             'conformance/limit_telemetry_sources.py','tests/test_limit_full_mapping.py')}},
        manual_decisions={
            'adjust-callable':'LRM p66 prose says SetLimits; Examples 103/104 and original API use AdjustLimits. The original callable and argument shape are exercised.',
            'yellow-key':'LRM p61 descriptive LoHigh conflicts with the declared LoYel modifier; LoHigh rejects atomically and LoYel succeeds.',
            'driver-profile':'Finite GENERIC driver capacities, registered limits:// JSON resources, activation expressions and hysteresis are defined in LIMIT_FEATURE_PROFILE.md; the original protobuf methods are retained.'},
        scope='Remaining LIMIT functions, examples, selectors, named definitions, four types and metadata; each maps to all four native dimensions.',
        full_v05_accepted=False,full_v06_accepted=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('raw','legacy','sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('revision','image'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=qualify(args.raw,args.legacy,args.sequence,args.revision,args.image,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
