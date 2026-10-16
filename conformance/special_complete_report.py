"""Full ranging, memory and TM/TC lookup contracts from native service evidence."""
import zipfile
from aggregate_support import (ROOT, PREFIX, DIMENSIONS, sha, read, ref,
    complete_sequence, dimensional_mapping, merge_review_inputs)

MAP = {}


def bind(names, suite, *features):
    for name in names:
        assert name not in MAP
        MAP[name] = tuple((suite, feature) for feature in features)


bind(('FUNCTION-ENABLERANGING','FUNCTION-DISABLERANGING','EXAMPLE-169',
      'SECTION-4-18-1-125'), 'ranging', 'schedule-dual')
bind(('FUNCTION-STARTRANGING','EXAMPLE-170','EXAMPLE-171'), 'ranging', 'dual','schedule-dual','status')
bind(('FUNCTION-ABORTRANGING','EXAMPLE-172'), 'ranging', 'dual','calibration','schedule-dual','status')
bind(('FUNCTION-SETBASEBANDCONFIG','FUNCTION-GETBASEBANDCONFIG','EXAMPLE-173',
      'SECTION-4-18-3-127'), 'ranging', 'baseband-batch','baseband-format')
bind(('FUNCTION-STARTRANGINGCALIBRATION','EXAMPLE-175'), 'ranging', 'calibration','status','schedule-dual')
bind(('FUNCTION-GETRANGINGSTATUS','EXAMPLE-176','CONSTANT-RANGING-STATE-ERROR',
      'CONSTANT-RANGING-STATE-IDLE','CONSTANT-RANGING-STATE-RANGING',
      'CONSTANT-RANGING-STATE-CALIBRATING','SECTION-4-18-4-128'), 'ranging','status')
bind(('SECTION-4-18-2-126',), 'ranging','dual','calibration','schedule-dual','status')
bind(('SECTION-4-18-124',), 'ranging','dual','calibration','schedule-dual','status','baseband-batch','baseband-format')
bind(('FUNCTION-GENERATEMEMORYREPORT','EXAMPLE-191','MODIFIER-DESTINATION',
      'SYNTAX-URI-MEM','SECTION-4-20-1-136'), 'memory','report')
bind(('FUNCTION-CANDIDATE-COMPAREMEMORYIMAGES','FUNCTION-COMPAREMEMORYIMAGE',
      'EXAMPLE-192','EXAMPLE-193','SECTION-4-20-2-137'), 'memory','compare')
bind(('FUNCTION-MEMORYLOOKUP','EXAMPLE-194','SECTION-4-20-3-138'), 'memory','lookup')
bind(('FUNCTION-TMTCLOOKUP','EXAMPLE-195','SECTION-4-21-1-140','SECTION-4-21-139'), 'memory','tmtc')
bind(('MODIFIER-IMAGE','SECTION-4-20-135'), 'memory','report','compare','lookup')
bind(('MODIFIER-BEGIN','MODIFIER-SOURCE'), 'memory','report','compare','lookup','tmtc')


def spelling(root=ROOT):
    from pypdf import PdfReader
    manual = root/'docs/reference/SPELL - Language Reference - 2.4.4.pdf'
    archive = root/'docs/reference/SPELL2.6.10-src.zip'
    pages = PdfReader(manual)
    prose, index = pages.pages[100].extract_text(), pages.pages[103].extract_text()
    assert 'CompareMemoryImages' in prose and 'Example 192' in prose and 'Example 193' in prose
    assert 'CompareMemoryImage Compare' in index
    member = 'src/spell/spell/lang/functions.py'
    with zipfile.ZipFile(archive) as z: source = z.read(member)
    assert source.count(b'def CompareMemoryImages(') == 1
    assert b'def CompareMemoryImage(' not in source
    import hashlib
    return dict(manual=ref(manual), archive=ref(archive), pages=[101,104], member=member,
        member_sha256=hashlib.sha256(source).hexdigest(),
        decision='The p104 index omits the final s; p101, both examples and the original callable use CompareMemoryImages. Both inventory identities retain evidence for that original callable.')


def qualify(sequence_path, native_wheel, driver_wheel):
    from ranging_complete_review import review as ranging_review
    from memory_complete_review import review as memory_review
    from rng_state_report import qualify as state_review
    from rng_report import qualify as catalog_review
    required = ('ranging-complete','memory-complete','rng-state','rng-catalog','common')
    sequence, paths, raws, inputs = complete_sequence(sequence_path, required)
    image, revision = sequence['image'], sequence['source_commit']
    wheels = dict(native_wheel=native_wheel, driver_wheel=driver_wheel)
    reviewed = dict(
        ranging=ranging_review(paths['ranging-complete'],None,revision,image,**wheels),
        memory=memory_review(paths['memory-complete'],None,None,None,revision,image,**wheels),
        state=state_review(raws['rng-state']), catalog=catalog_review(raws['rng-catalog']))
    assert len(reviewed['ranging']['checks']) == 24 and len(reviewed['memory']['checks']) == 32
    assert all(r['runtime_image'] == image for r in reviewed.values())
    assert all(reviewed[name]['composed_wheels']['passed'] for name in ('memory','ranging'))
    checks = dimensional_mapping(MAP, reviewed)
    inventory = {r['id']:r for r in read(ROOT/'conformance/inventory.json')['rows']}
    assert len(MAP) == 45 and {PREFIX+name for name in MAP} <= set(inventory)
    merge_review_inputs(inputs, reviewed.values())
    for name in ('conformance/special_complete_report.py','conformance/ranging_complete_review.py',
                 'conformance/memory_complete_review.py','tests/test_special_complete_mapping.py'):
        inputs[name] = sha(ROOT/name)
    return dict(passed=True, runtime_image=image, source_revision=revision, checks=checks, inputs=inputs,
        qualified_contracts=sorted(PREFIX+name for name in MAP), sequence=ref(sequence_path),
        raw={name:ref(path) for name,path in paths.items()}, independent_reviews=reviewed,
        manual_decisions=dict(compare_memory_spelling=spelling()), full_v05_accepted=False,
        scope='All memory/ranging and TM/TC lookup clauses in the documented GENERIC simulator profile; binary reference images, ASCII reports, RAW/ENG data, exact driver receipts and independent schedule/activity states.')


if __name__ == '__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser()
    for name in ('sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
