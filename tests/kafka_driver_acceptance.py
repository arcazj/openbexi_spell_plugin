"""Explicit real Kafka qualification, using a uniquely owned loopback broker."""
import json
import socket
import subprocess
import threading
import time
import uuid
import pytest
from kafka import KafkaConsumer,KafkaProducer
from kafka.admin import KafkaAdminClient
from dss.engine import DssEngine
from dss.server import DssRuntime,ApiServer,TcServer
from openbexi_spell_dss.codec import pack
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher,PREFIX
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p

IMAGE = 'apache/kafka:4.3.1@sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837'


def docker(*args):
    result = subprocess.run(['docker',*args],capture_output=True,timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-2000:])
    return result.stdout


def wait(predicate,timeout=30):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('Kafka qualification deadline expired')


@pytest.fixture
def broker():
    identity = uuid.uuid4().hex
    name = 'openbexi-v04-kafka-'+identity
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port = probe.getsockname()[1]
    endpoint = '127.0.0.1:'+str(port)
    env = dict(CLUSTER_ID='4L6g3nShT-eMCtK--X86sw',KAFKA_NODE_ID='1',KAFKA_PROCESS_ROLES='broker,controller',
        KAFKA_LISTENERS='PLAINTEXT://:9092,CONTROLLER://:9093',KAFKA_ADVERTISED_LISTENERS='PLAINTEXT://'+endpoint,
        KAFKA_CONTROLLER_QUORUM_VOTERS='1@127.0.0.1:9093',
        KAFKA_LISTENER_SECURITY_PROTOCOL_MAP='CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT',
        KAFKA_CONTROLLER_LISTENER_NAMES='CONTROLLER',KAFKA_INTER_BROKER_LISTENER_NAME='PLAINTEXT',
        KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR='1',KAFKA_OFFSETS_TOPIC_NUM_PARTITIONS='1',
        KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR='1',KAFKA_TRANSACTION_STATE_LOG_MIN_ISR='1',
        KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS='0',KAFKA_NUM_PARTITIONS='1',
        KAFKA_HEAP_OPTS='-Xms128m -Xmx256m')
    args = [v for k,value in env.items() for v in ('-e',k+'='+value)]
    container = docker('run','-d','--name',name,'--label','org.openbexi.qualification='+identity,
        '--memory=768m','--cpus=1','-p','127.0.0.1:'+str(port)+':9092',*args,IMAGE).decode().strip()
    try:
        def ready():
            try:
                admin = KafkaAdminClient(bootstrap_servers=endpoint,request_timeout_ms=1500,bootstrap_timeout_ms=1500)
                try:
                    return bool(admin.describe_cluster().get('brokers'))
                finally:
                    admin.close()
            except Exception:
                return False
        wait(ready,timeout=90)
        yield endpoint
    finally:
        info = json.loads(docker('inspect',container))[0]
        assert info['Config']['Labels']['org.openbexi.qualification'] == identity
        docker('rm','--force','--volumes',container)


def test_binary_outbox_kafka_freshness_duplicates_and_clock_task(broker,tmp_path):
    engine = DssEngine(tmp_path/'dss.sqlite')
    runtime = DssRuntime(engine,bootstrap_servers=broker,test_control=True,tick_seconds=.1)
    tcp,http = TcServer(('127.0.0.1',0),runtime),ApiServer(('127.0.0.1',0),runtime)
    runtime.tc_address = tcp.server_address
    threads = [threading.Thread(target=s.serve_forever) for s in (tcp,http)]
    for thread in threads:
        thread.start()
    runtime.start()
    transport,journal,producer = None,None,None
    try:
        wait(lambda:runtime.health()['status']=='ready')
        transport = Transport.from_binding(dict(url='http://127.0.0.1:'+str(http.server_port),
            host=tcp.server_address[0],port=tcp.server_address[1],kafka=broker))
        journal = Journal(tmp_path/'effects.sqlite')
        dispatcher = Dispatcher(transport,journal)
        who = dict(session=uuid.uuid4().hex,procedure=uuid.uuid4().hex,definition='kafka-qualified',version='a'*64,
                   controller_epoch=1,procedure_fence=1,mode='Development',release=None)
        def call(family,method,request):
            return dispatcher.dispatch('/'+PREFIX+'_'+family+'/'+method,request.SerializeToString(),who,uuid.uuid4().hex,lambda:None)
        item = runtime.database.telemetry[0]['item_id']
        transport.sample(item,timeout=10)
        initial = transport.telemetry.sequence
        original = bytes.fromhex(engine.telemetry()['packet_hex'])
        producer = KafkaProducer(bootstrap_servers=broker,acks='all')
        producer.send('openbexi.GENERIC.tm',key=transport.epoch.encode(),value=original).get(timeout=5)
        time.sleep(.3)
        assert transport.telemetry.sequence == initial
        call('TASK','StartTask',p.Task(name='DSS_CLOCK'))
        assert engine.state()['running'] is True
        transport.sample(item,wait=True,timeout=5)
        assert transport.telemetry.sequence > initial
        call('TASK','StopTask',p.Task(name='DSS_CLOCK'))
        assert engine.state()['running'] is False
        call('TC','SendCommand',p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1'),args=pack([])))
        assert engine.state()['core']['commands_executed'] == 1
        wait(lambda:engine.outbox_status()['pending_packets']==0)
        evidence = engine.evidence(engine.state()['scenario_id'])
        assert len(evidence['operations']) == 5
        assert all(row['published'] for row in evidence['packets'])
        assert all(row['ingress_delivery_count']==1 for row in evidence['operations'])
        assert transport.error is None
    finally:
        if transport:
            transport.close()
        if producer:
            producer.close(timeout=3)
        if journal:
            journal.close()
        runtime.stop()
        for service in (http,tcp):
            service.shutdown()
            service.server_close()
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
        assert all(not thread.is_alive() for thread in runtime.threads)
        engine.close()
