"""One disposable, real DSS and original-schema driver per teaching session."""
import json
from pathlib import Path
import threading
import uuid

from dss.local import create_servers
from dss.engine import DssConflict
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.operational_journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server


class DemoDss:
    def __init__(self, directory, definition, mode='Development'):
        if mode not in {'Development', 'Monitoring'}:
            raise ValueError('Learning DSS supports Development or read-only Monitoring; Execution requires an approved release service')
        root = Path(directory)
        self.stop = threading.Event()
        self.runtime, self.tcp, self.api = create_servers(root / 'dss.sqlite', 0)
        self.threads = []
        for endpoint in (self.tcp, self.api):
            thread = threading.Thread(target=endpoint.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        transport = Transport('http://127.0.0.1:' + str(self.api.server_port), self.tcp.server_address)
        self.journal = Journal(root / 'driver.sqlite')
        dispatcher = Dispatcher(transport, self.journal)
        # The native resource helper updates existing GCS variables. Configure
        # teaching variables here; procedure writes still traverse original RPC.
        dispatcher.ground.update(lambda state: state['resources'].update({'value': 21, 'CMD_ACT_DEC': 'DEC2'}))
        identity = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex,
                        definition=definition, version='learning-desktop', controller_epoch=1,
                        procedure_fence=1, mode=mode, release=None)
        self.server = Server(lambda path, raw: dispatcher.dispatch(
            path, raw, identity, uuid.uuid4().hex, lambda: None))
        self.port = self.server.port
        # Procedures can inspect and configure only this disposable simulator.
        (root / 'simulator.json').write_text(json.dumps({
            'url': 'http://127.0.0.1:' + str(self.api.server_port),
            'profile': 'synthetic-learning', 'mode': mode, 'tick_seconds': .5}), encoding='utf-8')
        self.clock_error = None
        self.clock = threading.Thread(target=self.tick, name='learning-dss-clock')
        self.clock.start()

    def tick(self):
        while not self.stop.wait(.5):
            try:
                state = self.runtime.engine.state()
                self.runtime.engine.control('STEP', state['epoch'], state['revision'])
            except DssConflict:
                # A simultaneous command or explicit scenario reset wins.
                continue
            except Exception as error:
                self.clock_error = error
                return

    def close(self):
        self.stop.set()
        self.clock.join(timeout=5)
        self.server.close()
        self.runtime.stop_event.set()
        for endpoint in (self.tcp, self.api):
            endpoint.shutdown()
            endpoint.server_close()
        for thread in self.threads:
            thread.join(timeout=5)
        self.journal.close()
        self.runtime.engine.close()
        if self.clock_error:
            raise RuntimeError('Simulator clock failed') from self.clock_error
