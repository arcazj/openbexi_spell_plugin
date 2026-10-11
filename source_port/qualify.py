"""Independent installed-wheel checks for the original-source RPC foundation.

SPDX-License-Identifier: GPL-3.0-or-later
Run with an isolated interpreter: python -I source_port/qualify.py --output OUTPUT
The fixture implements the original driver lifecycle, not a replacement manager.
These checks do not establish native executor or complete language conformance.
"""
import argparse
import builtins
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib import import_module, metadata
import json
import os
from pathlib import Path
import sys
import uuid
import zipfile

import grpc
from google.protobuf.empty_pb2 import Empty
import spell
import spell_source_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run = root / ('source-fixture-' + uuid.uuid4().hex)
    run.mkdir()
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    check('CPython 3.13', sys.version_info[:2] == (3, 13))
    check('installed source wheel', 'site-packages' in spell.__file__)
    check('alpha foundation identity', metadata.version('openbexi-spell-source') == '0.2.0a1')
    try:
        metadata.version('openbexi-spell-plugin')
    except metadata.PackageNotFoundError:
        checks.append('bounded alias absent from isolated environment')
    else:
        raise AssertionError('Conflicting bounded spell namespace installed')
    provenance = Path(spell_source_provenance.__file__).parent
    manifest = json.loads((provenance / 'manifest.json').read_text())
    sha = lambda data: hashlib.sha256(data).hexdigest()
    archive = provenance / 'SPELL2.6.10-src.zip'
    check('exact corresponding archive', sha(archive.read_bytes()) == manifest['archive_sha256'])
    package = Path(spell.__file__).parent.parent
    for item in manifest['sources'].values():
        check('source hash: ' + item['wheel_path'], sha((package / item['wheel_path']).read_bytes()) == item['sha256'])
    for name, item in manifest['generated'].items():
        check('generated hash: ' + name, sha((package / name).read_bytes()) == item['sha256'])
    before = dict(vars(builtins))
    from spell.utils.log import LOG
    LOG.showLog = False
    from spell.lib.registry import REGISTRY, RegistryError
    from spell.lib.factory import Factory, FactoryError
    from spell.lib.drivermgr import DriverManager
    from spell.config.reader import Config
    from spell.lib.adapter.config import Configurable
    from spell.lang import functions, constants
    from spell.utils.grpc_utils import GRPCThreadPool, PackValue, UnpackValue
    from spell.stubs import SPELLDriver_pb2 as messages, SPELLDriver_pb2_grpc as services
    for schema in ('SPELLExecutor', 'SPELLService'):
        import_module('spell.stubs.' + schema + '_pb2')
        import_module('spell.stubs.' + schema + '_pb2_grpc')
    # Every language helper is actual upstream source, not the bounded SDK.
    helpers = sorted((Path(spell.__file__).parent / 'lang/helpers').glob('*.py'))
    for path in helpers:
        import_module('spell.lang.helpers.' + path.stem)
    check('original helper/function imports', all(callable(getattr(functions, n)) for n in ('Display','GetTM','BuildTC','Send')))
    check('no builtins injection', before == vars(builtins))
    for native in ('DataContainer', 'Var'):
        try:
            getattr(constants, native)
        except ImportError as exc:
            check('native ' + native + ' fails clearly', 'not qualified' in str(exc))
        else:
            raise AssertionError('Native type silently substituted: ' + native)
    try:
        functions.GetTM('TM1')
    except RegistryError as exc:
        check('context-bound function requires CTX injection', 'CTX' in str(exc))
    else:
        raise AssertionError('Original function ran without an executor')
    configure = Configurable()
    configure.setConfig({'owner':'object','object_only':3})
    kwargs = {'owner':'keyword','config':{'owner':'config','config_only':4}}
    value = configure.buildConfig(({'owner':'argument','argument_only':5},),kwargs,
        secondary={'owner':'secondary','secondary_only':2},defaults={'owner':'default','default_only':1})
    check('original modifier precedence', value == {'owner':'keyword','default_only':1,
        'secondary_only':2,'object_only':3,'config_only':4,'argument_only':5})
    values = [None, True, False, 0, -(2**63), 2**63-1, 3.125, 'café 😀',
        [None,False,42,'Unicode'], {'nested':[1,{'x':3.5}],'key':'value'}]
    for index, value in enumerate(values):
        check('original RPC value roundtrip ' + str(index), UnpackValue(PackValue(value)) == value)
    with GRPCThreadPool('source-probe', max_workers=4) as pool:
        futures = [pool.submit(lambda x: x*x, n) for n in range(32)]
        check('public stdlib thread pool runs all work', [f.result(timeout=5) for f in futures] == [n*n for n in range(32)])
        broken = pool.submit(lambda: 1/0)
        try:
            broken.result(timeout=5)
        except ZeroDivisionError:
            checks.append('thread pool propagates errors')
        else:
            raise AssertionError('Worker exception lost')

    config_root = run / 'config'
    (config_root / 'spell').mkdir(parents=True)
    (config_root / 'contexts').mkdir()
    driver_root = run / 'drivers'
    driver = driver_root / 'source_probe'
    driver.mkdir(parents=True)
    (driver / '__init__.py').write_text('TRACE=[]\n',encoding='utf-8')
    for family, module, base_module, base in (
        ('CONFIG','config','config','ConfigInterface'), ('TM','tm','tm','TmInterface'), ('TC','tc','tc','TcInterface')):
        shutdown = ', shutdown=False' if family == 'CONFIG' else ''
        (driver / (module + '.py')).write_text(
            f"from spell.lib.adapter.{base_module} import {base}\nfrom . import TRACE\n"
            f"class Probe({base}):\n"
            "    def setup(self,ctx,drv):\n"
            f"        TRACE.append(('setup','{family}'))\n        super().setup(ctx,drv)\n"
            f"    def cleanup(self{shutdown}):\n        TRACE.append(('cleanup','{family}'))\n"
            f"    def onCommand(self,value):\n        TRACE.append(('command','{family}',value))\n"
            f"{family}=Probe()\n", encoding='utf-8')
    with zipfile.ZipFile(archive) as z:
        for source, target in (('config/spell/language.xml',config_root/'spell/language.xml'),
            ('config/contexts/context_example.xml',config_root/'contexts/context_example.xml')):
            target.write_bytes(z.read(source))
    (config_root / 'spell/driver_example.xml').write_text(
        '<driver id="source_probe"><name>Source probe</name><interfaces>TM,TC</interfaces>'
        '<path>' + driver_root.as_posix() + '</path><properties/></driver>',encoding='utf-8')
    context_path = config_root / 'contexts/context_example.xml'
    context_text = context_path.read_text().replace('<driver>example</driver>', '<driver>source_probe</driver>')
    context_text = context_text.replace('<driverconfig>', '<driverconfig><property name="CWS">DSS</property>')
    # The original source carries site-specific data-source defaults. The local
    # test supplies explicit loopback sources and never contacts those defaults.
    context_text = context_text.replace('<databases>', '<databases>' + ''.join(
        '<datasource name="' + name + '"><dataserver name="Local fixture" host="http://127.0.0.1" serviceUrl="/disabled"/></datasource>'
        for name in ('PHAROS','EXTERNAL')))
    context_path.write_text(context_text,encoding='utf-8')
    server_path = config_root / 'server.xml'
    with zipfile.ZipFile(archive) as z:
        server_path.write_bytes(z.read('config/server/server_example.xml'))
    os.environ['SPELL_CONFIG'] = str(config_root)
    os.environ['SPELL_HOME'] = str(run)
    os.environ['SPELL_DATA'] = str(run / 'data')
    Config.instance().load(str(server_path))
    check('original XML configuration loaded', Config.instance().readOk)
    manager = DriverManager.instance()
    try:
        manager.setup('example')
        trace = import_module('source_probe').TRACE
        check('factory creates configured driver', all(REGISTRY[n].__class__.__module__.startswith('source_probe.') for n in ('CONFIG','TM','TC')))
        check('setup proceeds forward', trace == [('setup','CONFIG'),('setup','TM'),('setup','TC')])
        check('original generic DBMGR appended', manager.interfaces == ['CONFIG','TM','TC','DBMGR'])
        try:
            functions.GetTM('TM1')
        except RegistryError as exc:
            check('executor-bound function requires EXEC injection', 'EXEC' in str(exc))
        else:
            raise AssertionError('Original function ran without an executor')
        manager.onCommand('PAUSE')
        check('command broadcast to driver', trace[-3:] == [('command','CONFIG','PAUSE'),('command','TM','PAUSE'),('command','TC','PAUSE')])
        check('cleanup succeeds', manager.cleanup(shutdown=True))
        check('cleanup proceeds reverse', trace[-3:] == [('cleanup','TC'),('cleanup','TM'),('cleanup','CONFIG')])
        first_interface = REGISTRY['TM']
        # A similarly named sibling path must survive cleanup; namespace modules
        # with no filename already exist in this real interpreter.
        sibling = str(driver_root) + '-sibling'
        sys.path.append(sibling)
        try:
            manager.cleanupCache()
            check('driver cache removes its own path', str(driver_root) not in sys.path)
            check('driver cache retains unrelated sibling', sibling in sys.path)
            check('driver modules removed', 'source_probe' not in sys.modules)
            manager.setup('example')
            check('driver reload creates a fresh interface', REGISTRY['TM'] is not first_interface)
            check('reload setup still forward', import_module('source_probe').TRACE == [('setup','CONFIG'),('setup','TM'),('setup','TC')])
            manager.cleanup(shutdown=True)
            manager.cleanupCache()
        finally:
            sys.path.remove(sibling)
    finally:
        if manager.loaded:
            manager.cleanup(force=True)
    REGISTRY['PROBE'] = object()
    check('registry retains object identity', REGISTRY.exists('PROBE'))
    REGISTRY.remove('PROBE')
    try:
        REGISTRY['PROBE']
    except RegistryError:
        checks.append('missing registry member raises')
    else:
        raise AssertionError('Removed registry member remained')
    try:
        Factory.instance().createInterface('UNKNOWN')
    except FactoryError:
        checks.append('factory rejects unknown interface family')
    else:
        raise AssertionError('Unknown service admitted')

    class Driver(services.SPELLDriverInterfaceServicer):
        def GetDriverInfo(self, request, context):
            result = messages.DriverInfo()
            result.CopyFrom(request)
            result.driverName = 'source-schema-probe'
            return result

        def Ping(self, request, context):
            return Empty()

    rpc = grpc.server(ThreadPoolExecutor(max_workers=2))
    services.add_SPELLDriverInterfaceServicer_to_server(Driver(),rpc)
    services.add_SPELLDriverInterface_TMServicer_to_server(services.SPELLDriverInterface_TMServicer(),rpc)
    port = rpc.add_insecure_port('127.0.0.1:0')
    rpc.start()
    try:
        with grpc.insecure_channel('127.0.0.1:' + str(port)) as channel:
            stub = services.SPELLDriverInterfaceStub(channel)
            info = stub.GetDriverInfo(messages.DriverInfo(host='café',port=port),timeout=3)
            check('actual generated gRPC roundtrip', info.host == 'café' and info.port == port and info.driverName == 'source-schema-probe')
            check('actual driver Ping', stub.Ping(Empty(),timeout=3) == Empty())
            try:
                services.SPELLDriverInterface_TMStub(channel).Setup(Empty(),timeout=3)
            except grpc.RpcError as exc:
                check('unsupported service returns UNIMPLEMENTED',exc.code() == grpc.StatusCode.UNIMPLEMENTED)
            else:
                raise AssertionError('Unimplemented service reported success')
    finally:
        rpc.stop(0).wait(timeout=5)
    service_counts = {name:len(service.methods) for name, service in messages.DESCRIPTOR.services_by_name.items()}
    check('all original driver service families generated', len(service_counts) == 11)
    result = {'version':'0.2.0a1','passed':True,'checks':checks,'check_count':len(checks),
        'python':sys.version,'origin':spell.__file__,'source_modules':len(manifest['sources']),
        'patched_modules':len(manifest['patches']),'rpc_schemas':3,'driver_services':service_counts,
        'native_supported':False,'operational_execution':False,'jetbrains_qualified':False}
    (root / 'source-installed.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('version','passed','check_count','source_modules','patched_modules','native_supported')}))


if __name__ == '__main__':
    main()
