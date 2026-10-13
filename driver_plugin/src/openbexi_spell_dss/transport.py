"""DSS/1 binary TC and immutable telemetry consumption, without command retries."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import socket
import threading
import time
from collections import OrderedDict
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from dss.catalog import SatelliteDatabase, canonical, validate_command
from dss.packets import decode_packet, decode_tm, encode_tc, recv_packet, TM_APID
from .journal import UncertainEffect


class Telemetry:
    """One epoch, monotonically ordered packets; exact duplicates are harmless."""
    def __init__(self, database, epoch):
        self.database, self.epoch = database, epoch
        self.sequence, self.digest, self.body = -1, None, None
        self.recent = OrderedDict()
        self.condition = threading.Condition()

    def accept(self, raw):
        packet = decode_packet(raw)
        body = packet.body
        if (packet.packet_type != 0 or packet.apid != TM_APID
                or body.get('schema_version') != 'openbexi.dss.tm/1'
                or body.get('database_digest') != self.database.digest
                or body.get('database_revision') != self.database.revision
                or body.get('satellite_epoch') != self.epoch):
            raise ValueError('Telemetry catalog/epoch/packet identity differs')
        sequence = body.get('tm_sequence')
        if type(sequence) is not int or sequence < 0 or packet.sequence != sequence & 0x3fff:
            raise ValueError('Invalid telemetry sequence')
        digest = hashlib.sha256(raw).hexdigest()
        with self.condition:
            if sequence in self.recent and digest != self.recent[sequence]:
                raise ValueError('Telemetry sequence reused with different bytes')
            if sequence < self.sequence:
                return False  # Kafka can replay old immutable outbox entries.
            if sequence == self.sequence:
                if digest != self.digest:
                    raise ValueError('Telemetry sequence reused with different bytes')
                return False
            self.sequence, self.digest, self.body = sequence, digest, body
            self.recent[sequence] = digest
            while len(self.recent) > 1024:
                self.recent.popitem(last=False)
            self.condition.notify_all()
            return True

    def sample(self, name):
        self.database.item(name)
        with self.condition:
            if self.body is None:
                raise ValueError('Telemetry unavailable')
            matches = [item for item in self.body['items'] if item['item_id'] == name]
            if len(matches) != 1:
                raise ValueError('Telemetry sample absent or ambiguous')
            return dict(matches[0], acquired_at_unix_ns=self.body['acquired_at_unix_ns'],
                        synchronization_state=self.body['synchronization_state'])


class Transport:
    @classmethod
    def from_binding(cls, settings):
        consumer = None
        if settings.get('kafka'):
            from kafka import KafkaConsumer
            consumer = KafkaConsumer('openbexi.GENERIC.tm', bootstrap_servers=settings['kafka'],
                group_id=None, auto_offset_reset='earliest', enable_auto_commit=False,
                fetch_max_bytes=131072, max_partition_fetch_bytes=131072, max_poll_records=32,
                request_timeout_ms=5000, bootstrap_timeout_ms=5000)
        try:
            return cls(settings['url'], (settings['host'], settings['port']), kafka=consumer)
        except BaseException:
            if consumer is not None:
                consumer.close()
            raise

    def __init__(self, url, tc_address, *, kafka=None):
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid service-owned DSS endpoint')
        self.url, self.tc_address = url.rstrip('/'), tuple(tc_address)
        self.database = SatelliteDatabase.load()
        state = self.get('state')
        if state['database_digest'] != self.database.digest or state['database_revision'] != self.database.revision:
            raise ValueError('DSS catalog identity differs')
        self.epoch, self.scenario = state['epoch'], state['scenario_id']
        self.telemetry = Telemetry(self.database, self.epoch)
        self.kafka, self.stop, self.thread, self.error = kafka, threading.Event(), None, None
        if kafka:
            self.thread = threading.Thread(target=self.consume, name='dss-driver-telemetry')
            self.thread.start()

    def get(self, path):
        with urlopen(Request(self.url + '/api/v1/' + path, headers={'Accept':'application/json'}), timeout=3) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError('DSS response bound exceeded')
            return json.loads(raw)

    def consume(self):
        try:
            while not self.stop.is_set():
                for records in self.kafka.poll(timeout_ms=100, max_records=32).values():
                    for record in records:
                        if record.key != self.epoch.encode():
                            continue
                        self.telemetry.accept(record.value)
        except BaseException as error:
            self.error = error

    def sample(self, name, *, wait=False, timeout=3):
        if type(wait) is not bool or type(timeout) not in {int,float} or not 0 < timeout <= 30:
            raise ValueError('Invalid telemetry wait/timeout')
        deadline = time.monotonic() + timeout
        # A cached sequence can lag the source while no procedure is reading.
        # Wait=True means the next source update after this acquisition starts,
        # so first bind to the current real snapshot, including an unread one.
        if wait and not self.kafka:
            self.telemetry.accept(bytes.fromhex(self.get('telemetry')['packet_hex']))
        initial = self.telemetry.sequence
        while True:
            if self.error:
                raise RuntimeError('Kafka telemetry consumer failed') from self.error
            if not self.kafka:
                self.telemetry.accept(bytes.fromhex(self.get('telemetry')['packet_hex']))
            if self.telemetry.body is not None and (not wait or self.telemetry.sequence > initial):
                return self.telemetry.sample(name)
            if time.monotonic() >= deadline:
                raise TimeoutError('No fresh telemetry sample before deadline')
            if self.stop.wait(.025):
                raise RuntimeError('DSS transport closed')

    def arguments(self, name, arguments):
        if type(arguments) is not list or len(arguments) > 16:
            raise ValueError('Command arguments must be a bounded original argument list')
        definitions = {item['name']:item for item in self.database.command(name)['arguments']}
        result = []
        for entry in arguments:
            if type(entry) is not list or not 2 <= len(entry) <= 3 or entry[0] not in definitions:
                raise ValueError('Invalid original command argument')
            key, value = entry[:2]
            config = entry[2] if len(entry) == 3 else {}
            if type(config) is not dict or set(config) - {'ValueFormat','ValueType','Radix'}:
                raise ValueError('Unsupported command argument modifier')
            kind = definitions[key]['value_type']
            wire_types = {'long':'LONG','float':'FLOAT','bool':'BOOLEAN','string':'STRING'}
            if wire_types.get(config.get('ValueType', next(k for k,v in wire_types.items() if v == kind))) != kind:
                raise ValueError('Command argument type differs from catalog')
            radix = {'dec':'DEC','hex':'HEX','oct':'OCT','bin':'BIN'}.get(config.get('Radix','dec'))
            if kind == 'LONG' and radix in {'HEX','OCT','BIN'}:
                encoded = {'HEX':lambda:f'0x{value:X}', 'OCT':lambda:f'0o{value:o}', 'BIN':lambda:f'0b{value:b}'}[radix]()
            elif kind == 'FLOAT':
                encoded = format(value, '.17g')
            elif kind == 'BOOLEAN':
                encoded = 'true' if value is True else 'false'
            else:
                encoded = str(value)
            result.append(dict(name=key, value=value, value_type=kind,
                               value_format={'Raw format':'RAW','Eng format':'ENG','Default format':'ENG'}.get(config.get('ValueFormat','Eng format')), radix=radix, encoded=encoded))
        validate_command(name, result)
        return result

    def command(self, name, arguments, identity, operation, check, *, timeout=5):
        arguments = self.arguments(name, arguments)
        state = self.get('state')
        if state['epoch'] != self.epoch or state['scenario_id'] != self.scenario:
            raise ValueError('DSS epoch changed; explicit rebinding required')
        digest = hashlib.sha256(canonical(dict(command_name=name, arguments=arguments,
                                               database_digest=self.database.digest))).hexdigest()
        base = dict(schema_version='openbexi.dss.tc/1', satellite_id='GENERIC',
            database_revision=self.database.revision, database_digest=self.database.digest,
            satellite_epoch=self.epoch, scenario_id=self.scenario, operation_id=operation,
            procedure_id=identity['definition'], execution_id=identity['procedure'],
            plan_id=operation, element_id='command-1', command_name=name,
            arguments=arguments, command_digest=digest)
        receipts, sent = [], False
        deadline = time.monotonic() + timeout
        stages = [('TRANSPORT','ACCEPTED'), ('LOADING','LOADED'), ('RELEASE','RELEASED'),
                  ('ACKNOWLEDGEMENT','ACKNOWLEDGED'), ('ONBOARD_EXECUTION','SUCCEEDED')]
        try:
            with socket.create_connection(self.tc_address, timeout=2) as connection:
                for sequence, (stage, expected) in enumerate(stages):
                    check()  # Live parent authority is checked before EVERY write.
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Command deadline expired')
                    connection.settimeout(min(3,remaining))
                    sent = True
                    connection.sendall(encode_tc(dict(base, stage=stage), sequence))
                    raw = recv_packet(connection, timeout=min(3,max(.001,deadline-time.monotonic())))
                    packet = decode_packet(raw)
                    answer = decode_tm(raw)
                    if (packet.apid != 102 or answer.get('schema_version') != 'openbexi.dss.ack/1'
                            or any(answer.get(key) != value for key, value in base.items() if key not in {'schema_version','arguments'})
                            or answer.get('stage') != stage):
                        raise ValueError('DSS acknowledgement binding differs')
                    receipts.append(answer)
                    if answer.get('outcome') != expected:
                        if answer.get('outcome') in {'MISSING','UNCERTAIN','INDETERMINATE'}:
                            raise UncertainEffect('DSS reported uncertain command outcome')
                        return False, receipts
            return True, receipts
        except BaseException as error:
            if sent:
                raise UncertainEffect('DSS command may have taken effect; no automatic replay') from error
            raise

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError('Kafka driver consumer shutdown unconfirmed')
        if self.kafka:
            self.kafka.close()
