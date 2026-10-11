import json,os,threading
from pathlib import Path
from dss.local import create_servers
from dss.packets import decode_tc
from openbexi_spell import BuildTC,GetTM,Send,Verify
from openbexi_spell_plugin.runtime import activate
runtime,tcp,api=create_servers(Path('/var/lib/dss/runtime-probe.sqlite'),0)
threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (tcp,api)]
for thread in threads: thread.start()
try:
    activate('http://127.0.0.1:'+str(api.server_port))
    assert runtime.health()['status']=='ready'
    assert runtime.health()['kafka_publisher'] is False
    value=GetTM('TM1')
    assert Verify('TM1',value)
    assert Send(BuildTC('CMD1'))
    state=runtime.engine.state()
    assert state['payload']['enabled'] is True
    assert state['core']['commands_executed']==1
    evidence=runtime.engine.evidence(state['scenario_id'])
    stages={decode_tc(bytes.fromhex(item['packet_hex']))['stage'] for item in evidence['operations']}
    expected={'TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION'}
    assert stages>=expected,stages
    report={'uid':os.getuid(),'health':'ready','command_effect':True,'commands_executed':1,
            'binary_stages':sorted(stages),'network':'none; in-container loopback','host_http_published':False}
finally:
    runtime.stop_event.set()
    for server in (api,tcp): server.shutdown();server.server_close()
    for thread in threads: thread.join(timeout=5);assert not thread.is_alive()
    runtime.engine.close()
report['owned_workers_joined']=True
print(json.dumps(report))
