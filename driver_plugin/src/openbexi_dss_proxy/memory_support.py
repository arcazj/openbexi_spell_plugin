"""Original memory RPCs and atomic reports at configured SPELL URI locations."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import uuid
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue, UnpackValue
from .common import POLICY
from .connection import call


def options(config,embedded):
    return {key:value for key,value in (config or {}).items() if key not in POLICY and key not in embedded}


def destination(context,uri):
    if type(uri) is not str or len(uri)>1024 or '://' not in uri:
        raise DriverException('Memory report requires a configured Destination URI')
    scheme,relative=uri.split('://',1)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}',scheme) or context.getLocationType(scheme)!='file':
        raise DriverException('Memory Destination must name a configured file location')
    if '\\' in relative or ':' in relative or '\x00' in relative:
        raise DriverException('Invalid memory report path')
    item=PurePosixPath(relative)
    if not relative or item.is_absolute() or any(part in ('','..','.') for part in relative.split('/')):
        raise DriverException('Memory report path must stay inside its configured location')
    configured=context.getLocationPath(scheme)
    if not configured:raise DriverException('Memory report location has no path')
    root=Path(configured)
    if not root.is_absolute():root=Path(os.environ['SPELL_DATA'])/root
    root=root.resolve()
    ext=context.getLocationExt(scheme)
    if ext:
        if not re.fullmatch(r'[A-Za-z0-9]{1,16}',ext):raise DriverException('Unsupported memory location extension')
        if not relative.endswith('.'+ext):relative+='.'+ext
    target=(root/relative).resolve()
    if target==root or not target.is_relative_to(root):raise DriverException('Memory report escapes its configured location')
    return target


def generate(owner,image,rtype,begin,end,source,config):
    wire=options(config,{'Image','Type','Begin','End','Source'})
    uri=wire.pop('Destination',None)
    if uri is None:
        return call('MEM','GenerateReport',p.MemoryReportRequest(image=image,report_type=rtype,
                    begin=str(begin),end=str(end),source=source,config=PackValue(wire))).value
    target=destination(owner.getContextConfig(),uri)
    # Reserve a writable temporary before the remote effect; retain an existing
    # destination until both RPCs and the complete ASCII write have succeeded.
    target.parent.mkdir(parents=True,exist_ok=True)
    report_id=uuid.uuid4().hex
    wire['ReportId']=report_id
    temporary=None
    try:
        descriptor,temporary=tempfile.mkstemp(prefix='.spell-memory-',dir=target.parent)
        with os.fdopen(descriptor,'wb') as stream:
            if not call('MEM','GenerateReport',p.MemoryReportRequest(image=image,report_type=rtype,
                    begin=str(begin),end=str(end),source=source,config=PackValue(wire))).value:return False
            value=UnpackValue(call('MEM','MemoryLookup',p.MemoryLookupRequest(name=report_id,image=image,report_type='REPORT',source=source)))
            if type(value) is not str:raise DriverException('Generated memory report is not ASCII text')
            encoded=value.encode('ascii')
            if len(encoded)>8192:raise DriverException('Generated memory report exceeds bound')
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target);temporary=None
        return True
    except (OSError,ValueError) as error:raise DriverException(str(error)) from error
    finally:
        if temporary is not None:Path(temporary).unlink(missing_ok=True)


def compare(image1,image2,rtype,begin,end,source,config):
    wire=options(config,{'Image','Type','Begin','End','Source'})
    return call('MEM','CompareImages',p.CompareMemoryReportRequest(image1=image1,image2=image2,
        report_type=rtype,begin=str(begin),end=str(end),source=source,config=PackValue(wire))).value


def capture(scp,filename,config):
    wire=options(config,{'Source','Name'})
    return call('MEM','CreateGoldenImage',p.GoldenImageRequest(scp=scp,filename=filename,config=PackValue(wire))).value


def lookup(name,address,image,rtype,source,config):
    wire=options(config,{'Name','Address','Image','Type','Source'})
    return UnpackValue(call('MEM','MemoryLookup',p.MemoryLookupRequest(name=name or '',address='' if address is None else str(address),
        image=image,report_type=rtype,source=source,config=PackValue(wire))))


def database(name,rtype,source,config):
    wire=options(config,{'Name','Type','Source'})
    if set(wire)-{'Begin','End','ValueFormat'}:raise DriverException('Unsupported database query modifier')
    if wire.get('ValueFormat','Eng format') not in ('Raw format','Eng format','Default format'):
        raise DriverException('Invalid database query value format')
    if 'Begin' in wire or 'End' in wire:
        name='OPENBEXI_TMTC_LOOKUP_1:'+json.dumps(dict(Name=name,Begin=wire.get('Begin',''),End=wire.get('End','')),separators=(',',':'))
    return UnpackValue(call('TM','DatabaseLookup',p.LookupRequest(name=name,type=rtype,source=source or '')).lookup)
