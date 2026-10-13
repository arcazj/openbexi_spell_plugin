"""Persist periodic ranging schedule independently of on-demand activity.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES={'openbexi_spell_dss/ground.py':'727669bbe36281faebbe7d5e53f9e1cf5db2d262ff7e9496e9aa89c3d9130880'}


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Unexpected ranging ground source: '+name)
    source=raw.decode('utf-8')
    before="                users=[],ranging='DISABLED',baseband={'DSS-BBE-1':{'frequency_hz':'1000000','integration_ms':'1000'}}))))"
    assert source.count(before)==1
    source=source.replace(before,"""                users=[],ranging='READY',ranging_schedule_enabled=False,
                baseband={'DSS-BBE-1':{'frequency_hz':'1000000','integration_ms':'1000'}}))))
            # LRM p93 separates the periodic plan from on-demand activities.
            # Migrate only this namespace and never reset an active operation.
            encoded,=journal.db.execute('SELECT state FROM ground WHERE namespace=?',(self.namespace,)).fetchone()
            state=json.loads(encoded)
            if type(state) is not dict:
                raise ValueError('Invalid ranging ground state object')
            activity=state.get('ranging')
            if 'ranging_schedule_enabled' not in state:
                if type(activity) is not str or activity not in {'DISABLED','READY','RANGING','CALIBRATING'}:
                    raise ValueError('Unknown legacy ranging state')
                state['ranging_schedule_enabled']=activity!='DISABLED'
                if activity=='DISABLED':
                    state['ranging']='READY'
                journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(canonical(state),self.namespace))
            elif (type(state['ranging_schedule_enabled']) is not bool
                  or type(activity) is not str or activity not in {'READY','RANGING','CALIBRATING'}):
                raise ValueError('Invalid separate ranging schedule/activity state')""")
    before="""            states = {'EnableRanging':'READY','DisableRanging':'DISABLED','AbortRanging':'READY',
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
                return transition"""
    after="""            states = {'AbortRanging':'READY','StartRanging':'RANGING','StartCalibration':'CALIBRATING'}
            schedules = {'EnableRanging':True,'DisableRanging':False}
            if method in states or method in schedules:
                if method in {'StartRanging','StartCalibration'} and (request.bbe != 'DSS-BBE-1' or request.antenna != 'DSS-ANTENNA-1'):
                    raise ValueError('Select the complete virtual ranging path')
                def transition():
                    def update(state):
                        if method in schedules:
                            state['ranging_schedule_enabled']=schedules[method]
                        else:
                            state['ranging']=states[method]
                        return True
                    return BoolValue(value=guarded_update(update))
                return transition"""
    assert source.count(before)==1
    source=source.replace(before,after)
    result=source.encode('utf-8')
    compile(result,name,'exec')
    return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    report={}
    for name,expected in PREIMAGES.items():
        target=site/name
        original=target.read_bytes()
        patched=apply(name,original)
        for label,contents in (('original',original),('patched',patched)):
            retained=evidence/label/name
            retained.parent.mkdir(parents=True,exist_ok=True)
            retained.write_bytes(contents)
        target.write_bytes(patched)
        report[name]=dict(preimage_sha256=expected,sha256=hashlib.sha256(patched).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    apply_tree(sys.argv[1],sys.argv[2])
