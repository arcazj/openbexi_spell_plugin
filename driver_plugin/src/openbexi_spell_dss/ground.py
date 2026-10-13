"""Declared GENERIC simulator ground services, scoped to one DSS epoch.

These are persistent simulator resources, snapshots and a virtual ranging path.
They do not represent an RF station, an OS shell, a printer or vendor Cortex.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import hmac
import json
import re
from urllib.request import Request,urlopen
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import BoolValue,Int32Value,StringValue
from .codec import pack,unpack
from .journal import canonical
from .stubs import SPELLDriver_pb2 as p


def name(value):
    if not isinstance(value,str) or re.fullmatch('[A-Za-z0-9_.-]{1,96}',value) is None:
        raise ValueError('Invalid simulator resource name')
    return value


class Ground:
    def __init__(self,transport,journal,users=None):
        self.transport,self.journal,self.users = transport,journal,users or {}
        self.namespace = hashlib.sha256((transport.url + '\0' + transport.epoch).encode()).hexdigest()
        with journal.transaction():
            journal.db.execute('CREATE TABLE IF NOT EXISTS ground(namespace TEXT PRIMARY KEY,state TEXT NOT NULL)')
            journal.db.execute('INSERT OR IGNORE INTO ground VALUES(?,?)',(self.namespace,canonical(dict(
                resources={},links={'TM':True,'TC':True},limits={},injections={},images={},reports={},displays={},
                users=[],ranging='DISABLED',baseband={'DSS-BBE-1':{'frequency_hz':'1000000','integration_ms':'1000'}}))))

    def state(self):
        with self.journal.lock:
            row = self.journal.db.execute('SELECT state FROM ground WHERE namespace=?',(self.namespace,)).fetchone()
            return json.loads(row[0])

    def update(self,action):
        with self.journal.transaction():
            state = self.state()
            result = action(state)
            raw = canonical(state)
            if len(raw) > 1024*1024 or any(len(state[key]) > 128 for key in ('resources','limits','injections','images','reports','displays','users')):
                raise ValueError('Simulator ground service capacity exceeded')
            self.journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(raw,self.namespace))
            return result

    def snapshot(self):
        state = self.transport.get('state')
        if state['epoch'] != self.transport.epoch:
            raise ValueError('Simulator ground epoch changed')
        return state

    def prepare(self,family,method,request,settings,check):
        def guarded_update(action):
            check()
            return self.update(action)
        if family == 'RSC':
            if settings and settings != {'IsLocal':False}:
                raise ValueError('Only the shared GENERIC simulator resource scope is available')
            if method in {'SetLink','CheckLink'}:
                if request.name not in {'TM','TC'}:
                    raise ValueError('Unknown simulator link')
                if method == 'CheckLink':
                    return lambda:BoolValue(value=self.state()['links'][request.name])
                def set_link():
                    guarded_update(lambda s:s['links'].__setitem__(request.name,request.status))
                    return BoolValue(value=True)
                return set_link
            if method == 'GetResources':
                return lambda:p.ResourcesRequest(value=pack(self.state()['resources']))
            key = name(request.name)
            if method == 'SetResource':
                value = unpack(request.value)
                canonical(value)  # Resource values are finite JSON in this profile.
                def set_resource():
                    guarded_update(lambda s:s['resources'].__setitem__(key,value))
                    return BoolValue(value=True)
                return set_resource
            def get_resource():
                resources = self.state()['resources']
                if key not in resources:
                    raise ValueError('Unknown simulator resource')
                if method == 'IsResourceOK':
                    return BoolValue(value=True)  # An existing typed persisted resource is available.
                return p.ResourceRequest(name=key,value=pack('AVAILABLE' if method == 'GetResourceStatus' else resources[key]))
            return get_resource
        if family == 'TASK':
            if settings and settings != {'Host':'DSS'}:
                raise ValueError('Host/printer routing is unavailable in the simulator profile')
            if method in {'StartTask','StopTask','CheckTask'}:
                if request.name != 'DSS_CLOCK':
                    raise ValueError('The only simulator task is DSS_CLOCK')
                if request.args.type_url and unpack(request.args) not in ('',[],None):
                    raise ValueError('DSS_CLOCK takes no arguments')
                if method == 'StartTask' and self.snapshot().get('transport',{}).get('automatic_clock') is False:
                    raise ValueError('Manual-clock DSS cannot start an automatic task')
                if method == 'CheckTask':
                    return lambda:Int32Value(value=1 if self.snapshot()['running'] else 0)
                def control():
                    state = self.snapshot()
                    body = dict(action='RESUME' if method == 'StartTask' else 'PAUSE',
                                expected_epoch=state['epoch'],expected_revision=state['revision'])
                    query = Request(self.transport.url+'/api/v1/control',data=canonical(body).encode(),headers={'Content-Type':'application/json'})
                    check()
                    with urlopen(query,timeout=3) as response:
                        result = json.loads(response.read(65537))
                    if result['epoch'] != state['epoch'] or result['running'] != (method == 'StartTask'):
                        raise ValueError('Simulator task control receipt differs')
                    return BoolValue(value=True)
                return control
            key = name(request.name)
            if key != 'DSS_TELEMETRY':
                raise ValueError('The only headless simulator display is DSS_TELEMETRY')
            def display():
                snapshot = self.transport.get('telemetry')
                def update(state):
                    if method == 'OpenDisplay':
                        state['displays'][key] = snapshot
                    elif method == 'CloseDisplay':
                        if key not in state['displays']:
                            raise ValueError('Display is not open')
                        del state['displays'][key]
                    elif method == 'PrintDisplay':
                        if key not in state['displays']:
                            raise ValueError('Display is not open')
                        state['reports']['display-'+key] = snapshot
                    else:
                        raise NotImplementedError(method)
                guarded_update(update)
                return Empty()
            return display
        if family == 'MEM':
            if settings:
                raise ValueError('Unsupported simulator memory modifier: '+','.join(sorted(settings)))
            if method == 'DataObjectLookup':
                if request.name != 'DSS_STATE' or request.type not in {'','JSON'}:
                    raise ValueError('Unknown simulator data object')
                return lambda:pack(self.snapshot())
            if method == 'DataItemLookup':
                if request.source not in {'','GENERIC'} or request.type not in {'','TM'} or request.valformat not in {'','Raw format','Eng format'}:
                    raise ValueError('Unsupported simulator data item lookup')
                self.transport.database.item(request.name)
                return lambda:pack(self.transport.sample(request.name)['raw' if request.valformat == 'Raw format' else 'engineering']['value'])
            if method == 'CreateGoldenImage':
                if request.scp != 'GENERIC':
                    raise ValueError('Unknown simulator spacecraft')
                key = name(request.filename)
                def golden():
                    snapshot = self.snapshot()
                    guarded_update(lambda s:s['images'].__setitem__(key,snapshot))
                    return BoolValue(value=True)
                return golden
            if request.source not in {'','GENERIC'} or request.report_type not in {'','JSON'}:
                raise ValueError('Only GENERIC JSON memory snapshots are available')
            if method == 'MemoryLookup':
                if request.name not in {'','DSS_STATE'} or request.address:
                    raise ValueError('Raw-address memory lookup is unavailable')
                key = name(request.image)
                return lambda:pack(self.state()['images'][key])
            if request.begin or request.end:
                raise ValueError('Byte ranges do not apply to JSON snapshots')
            if method == 'CompareImages':
                first,second = name(request.image1),name(request.image2)
                return lambda:BoolValue(value=self.state()['images'][first] == self.state()['images'][second])
            if method == 'GenerateReport':
                key = name(request.image)
                def report():
                    guarded_update(lambda s:s['reports'].__setitem__(key,s['images'][key]))
                    return BoolValue(value=True)
                return report
        if family == 'USER':
            if settings:
                raise ValueError('Unsupported simulator user modifier')
            key = name(request.username)
            if method == 'IsLoggedIn':
                return lambda:BoolValue(value=key in self.state()['users'])
            if method == 'Login':
                verifier = self.users.get(key)
                if not verifier or not hmac.compare_digest(hashlib.sha256(request.password.encode()).hexdigest(),verifier):
                    raise PermissionError('Simulator account credentials rejected')
                def login():
                    guarded_update(lambda s:s['users'].append(key) if key not in s['users'] else None)
                    return BoolValue(value=True)
                return login
            if method == 'Logout':
                def logout():
                    def update(state):
                        if key not in state['users']:
                            return False
                        state['users'].remove(key)
                        return True
                    return BoolValue(value=guarded_update(update))
                return logout
        if family == 'RNG':
            if settings:
                raise ValueError('Unsupported virtual ranging modifier')
            if method == 'UpdateCortexConf':
                raise NotImplementedError('GENERIC has no vendor Cortex device')
            if method in {'GetAntennaNames','GetBasebandNames','GetRangingPaths'}:
                values = {'GetAntennaNames':['DSS-ANTENNA-1'],'GetBasebandNames':['DSS-BBE-1'],
                          'GetRangingPaths':['DSS-BBE-1/DSS-ANTENNA-1']}
                return lambda:p.Names(names=values[method])
            if method == 'GetRangingStatus':
                return lambda:StringValue(value=self.state()['ranging'])
            if method in {'GetBasebandConfig','SetBasebandConfig'}:
                if request.bbe != 'DSS-BBE-1' or request.param not in {'frequency_hz','integration_ms'}:
                    raise ValueError('Unknown virtual baseband parameter')
                if method == 'GetBasebandConfig':
                    return lambda:p.BaseBandConfig(bbe=request.bbe,param=request.param,value=self.state()['baseband'][request.bbe][request.param])
                if not request.value.isascii() or not request.value.isdigit() or not 1 <= int(request.value) <= 1000000000:
                    raise ValueError('Invalid virtual baseband integer')
                def set_baseband():
                    guarded_update(lambda s:s['baseband'][request.bbe].__setitem__(request.param,request.value))
                    return BoolValue(value=True)
                return set_baseband
            if request.bbe not in {'','DSS-BBE-1'} or request.antenna not in {'','DSS-ANTENNA-1'}:
                raise ValueError('Unknown virtual ranging path')
            states = {'EnableRanging':'READY','DisableRanging':'DISABLED','AbortRanging':'READY',
                      'StartRanging':'RANGING','StartCalibration':'CALIBRATING'}
            if method in states:
                if method in {'StartRanging','StartCalibration'} and (request.bbe != 'DSS-BBE-1' or request.antenna != 'DSS-ANTENNA-1'):
                    raise ValueError('Select the complete virtual ranging path')
                def transition():
                    def update(state):
                        if method in {'StartRanging','StartCalibration','AbortRanging'} and state['ranging'] == 'DISABLED':
                            return False
                        state['ranging'] = states[method]
                        return True
                    return BoolValue(value=guarded_update(update))
                return transition
        raise NotImplementedError(family+'.'+method)
