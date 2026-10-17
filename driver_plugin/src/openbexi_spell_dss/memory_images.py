"""GENERIC reference memory, backed by retained immutable DSS binary packets."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
from google.protobuf.wrappers_pb2 import BoolValue
from dss.packets import decode_tm
from .codec import pack
from .ground import name

PROFILE='openbexi.spell.memory-image/1'
LOOKUP_PREFIX='OPENBEXI_TMTC_LOOKUP_1:'
FORMATS={'','Default format','Raw format','Eng format'}


def address(value):
    if type(value) is int:
        number=value
    elif type(value) is str and re.fullmatch(r'(?:0[xX][0-9a-fA-F]{1,8}|[0-9]{1,10})',value):
        number=int(value,16 if value.lower().startswith('0x') else 10)
    else:raise ValueError('Memory address must be an unsigned integer or decimal/hex address')
    if not 0<=number<=0xffffffff:raise ValueError('Memory address outside unsigned 32-bit range')
    return number


def bounds(begin='',end=''):
    lo=0 if begin in ('',None) else address(begin)
    hi=0xffffffff if end in ('',None) else address(end)
    if lo>hi:raise ValueError('Memory Begin exceeds End')
    return lo,hi


def image(ground,key):
    images=ground.state()['images'];key=name(key)
    if key not in images:raise ValueError('Unknown reference memory image')
    return images[key]


def packet(ground,record):
    if record.get('schema')!=PROFILE:raise ValueError('Reference image is not a TM binary image')
    data=bytes.fromhex(record['packet_hex'])
    if len(data)>65536 or hashlib.sha256(data).hexdigest()!=record['sha256']:
        raise ValueError('Reference memory image digest differs')
    body=decode_tm(data)
    if (body['database_digest']!=ground.transport.database.digest or
        body['database_revision']!=ground.transport.database.revision or
        body['satellite_epoch']!=ground.transport.epoch):
        raise ValueError('Reference image catalog or epoch differs')
    return body


def selection(ground,record,begin='',end='',mnemonic='',at='',value_format='Eng format'):
    if value_format not in FORMATS:raise ValueError('Unsupported memory value format')
    lo,hi=bounds(begin,end)
    if at not in ('',None):lo=hi=address(at)
    items=packet(ground,record)['items']
    if mnemonic:ground.transport.database.item(mnemonic)
    selected=[];seen=set()
    for item in items:
        identity=item['item_id']
        if identity in seen:raise ValueError('Duplicate reference memory datum')
        seen.add(identity)
        code=ground.transport.database.item(identity)['item_code']
        if lo<=code<=hi and (not mnemonic or mnemonic==identity):
            value=item['raw' if value_format=='Raw format' else 'engineering']['value']
            selected.append((code,identity,value))
    if mnemonic and mnemonic not in seen:raise ValueError('Named datum is absent from reference image')
    if at not in ('',None) and not selected:raise ValueError('Unknown reference memory address')
    return sorted(selected)


def content(ground,record,rtype,begin,end,value_format):
    if rtype in ('','JSON') and record.get('schema')!=PROFILE:
        if begin or end:raise ValueError('Address ranges do not apply to JSON snapshots')
        return json.dumps(record,sort_keys=True,ensure_ascii=True,separators=(',',':'))+'\n'
    if rtype not in ('','TM'):raise ValueError('Unsupported reference memory type')
    return ''.join(str(code)+'\t'+key+'\t'+json.dumps(value,ensure_ascii=True,separators=(',',':'))+'\n'
                   for code,key,value in selection(ground,record,begin,end,value_format=value_format))


def prepare(ground,method,request,settings,check):
    def update(action):check();return ground.update(action)
    if method=='CreateGoldenImage':
        if request.scp!='GENERIC' or set(settings)-{'Type'}:raise ValueError('Unsupported reference image source/modifier')
        rtype=settings.get('Type','JSON');key=name(request.filename)
        if rtype not in ('JSON','TM'):raise ValueError('Unsupported reference memory type')
        def capture():
            if rtype=='JSON':record=ground.snapshot()
            else:
                sample=ground.transport.get('telemetry')
                data=bytes.fromhex(sample['packet_hex'])
                record=dict(schema=PROFILE,packet_hex=data.hex(),sha256=hashlib.sha256(data).hexdigest())
                packet(ground,record)
            update(lambda state:state['images'].__setitem__(key,record))
            return BoolValue(value=True)
        return capture
    if method not in {'MemoryLookup','CompareImages','GenerateReport'}:
        return None  # Original data-object/item profile remains available.
    if request.source not in ('','GENERIC'):raise ValueError('Unsupported reference memory source')
    rtype=request.report_type
    if rtype=='REPORT' and method=='MemoryLookup':
        if settings or request.address:raise ValueError('Unsupported report retrieval modifier')
        key='memory-'+name(request.name)
        def report():
            row=ground.state()['reports'].get(key)
            if not row or row.get('image')!=request.image:raise ValueError('Unknown generated memory report')
            return pack(row['content'])
        return report
    if rtype not in ('','JSON','TM'):raise ValueError('Unsupported reference memory type')
    allowed={'ValueFormat'} | ({'Begin','End'} if method=='MemoryLookup' else {'ReportId'} if method=='GenerateReport' else set())
    if set(settings)-allowed:raise ValueError('Unsupported memory modifier')
    value_format=settings.get('ValueFormat','Eng format')
    if value_format not in FORMATS:raise ValueError('Unsupported memory value format')
    if method=='MemoryLookup':
        begin,end=settings.get('Begin',''),settings.get('End','');bounds(begin,end)
        record=image(ground,request.image)
        if record.get('schema')!=PROFILE:
            if rtype=='TM' or request.name not in ('','DSS_STATE') or request.address or begin or end:
                raise ValueError('JSON snapshots require a whole-object lookup')
            return lambda:pack(record)
        if rtype=='JSON':raise ValueError('JSON type does not select a TM binary image')
        rows=selection(ground,record,begin,end,request.name,request.address,value_format)
        return lambda:pack({key:value for _,key,value in rows})
    begin,end=request.begin,request.end;bounds(begin,end)
    if method=='CompareImages':
        first=image(ground,request.image1);second=image(ground,request.image2)
        if (first.get('schema')==PROFILE)!=(second.get('schema')==PROFILE):
            raise ValueError('Reference image types differ')
        a=content(ground,first,rtype,begin,end,value_format)
        b=content(ground,second,rtype,begin,end,value_format)
        return lambda:BoolValue(value=a==b)
    record=image(ground,request.image)
    text=content(ground,record,rtype,begin,end,value_format)
    # The original Any response scalar bound applies to retrieved ASCII reports.
    if len(text.encode('ascii'))>8192:raise ValueError('Memory report exceeds 8192 ASCII bytes')
    report_id=settings.get('ReportId')
    key='memory-'+name(report_id) if report_id is not None else name(request.image)
    value=dict(image=request.image,content=text,sha256=hashlib.sha256(text.encode('ascii')).hexdigest()) if report_id is not None else record
    def generate():
        update(lambda state:state['reports'].__setitem__(key,value))
        return BoolValue(value=True)
    return generate


def database_lookup(database,request,command_lookup):
    if request.source not in ('','GENERIC') or request.type not in ('TM','TC'):
        raise ValueError('Unsupported database lookup source/type')
    mnemonic=request.name;lo,hi=0,0xffffffff
    bounded=mnemonic.startswith(LOOKUP_PREFIX)
    if bounded:
        text=mnemonic[len(LOOKUP_PREFIX):]
        if len(text)>4096:raise ValueError('Database query exceeds bounds')
        query=json.loads(text)
        if type(query) is not dict or set(query)!={'Name','Begin','End'} or type(query['Name']) is not str:
            raise ValueError('Invalid database lookup envelope')
        mnemonic=query['Name'];lo,hi=bounds(query['Begin'],query['End'])
    if mnemonic:
        item=database.item(mnemonic) if request.type=='TM' else command_lookup(database,mnemonic)
        # Native command expansion uses this original-schema endpoint too.
        # A sequence has no address; only an unbounded catalog lookup selects it.
        if request.type=='TC' and item.get('kind')=='SEQUENCE' and not bounded:
            return item
        key='item_code' if request.type=='TM' else 'command_code'
        if key not in item:raise ValueError('Database query requires a concrete TM/TC entry')
        return item if lo<=item[key]<=hi else {}
    # Empty names select a bounded, explicit table; no expression execution.
    table=database.telemetry if request.type=='TM' else database.commands
    code='item_code' if request.type=='TM' else 'command_code'
    key='item_id' if request.type=='TM' else 'name'
    result={item[key]:item for item in table if lo<=item[code]<=hi}
    pack(result)  # Reject unsupported result size before constructing a response.
    return result
