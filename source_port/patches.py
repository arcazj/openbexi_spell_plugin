"""Small source-derived port patches. SPDX-License-Identifier: GPL-3.0-or-later.

Each edit checks its exact upstream preimage. Native DTA stays unavailable until
its real library builds and passes independent tests; no substitute is provided.
"""
import hashlib


PREIMAGES = {
    'spell/utils/spell_service.py': 'a317ec316e9a4a7142bfe8846a3120e3bd507dbb9b945f24ed51388f4b6a625f',
    'spell/lang/constants.py': '0a343ec475546ea1020d6558019f520f686c90304904bd4dcf67efb7ce57cbc9',
    'spell/lib/adapter/data.py': 'a8bc31980e239dbf89a9b348eaa7e9bd58e501eaf555bf2aaa87bcf0e61e5a03',
    'spell/utils/grpc_utils.py': 'aa6c7f35a2159c4dbd8d98422be7a606b7061d3aba043c738900c1eab19e7049',
    'spell/lib/adapter/databases/datasource.py': 'b56390eead7d8c3536aa4b06d24b8a0331a6717fecb9b1f56bfae94f4d894a96',
    'spell/lib/drivermgr.py': '6926dff1c3a51895263ea79845d9462f5f10e58f07f51fe866882209b2032594',
}


def apply(name, original):
    if name not in PREIMAGES:
        return original
    if hashlib.sha256(original).hexdigest() != PREIMAGES[name]:
        raise ValueError('Upstream patch preimage changed: ' + name)
    text = original.decode('utf-8')
    if name == 'spell/lib/adapter/data.py':
        start = text.index('import sys\n')
        text = text[:start] + '''# The source-derived CPython 3.13 port requires the real native library.
# Import failure must not silently turn DataContainer and Var into dictionaries.
try:
    import libSPELL_DTA_v3 as libSPELL_DTA
except ImportError as exc:
    raise ImportError("Native SPELL DTA is not qualified for this interpreter; "
                      "DataContainer and Var are unavailable") from exc

__all__ = ['DataContainer', 'Var']
DataContainer = libSPELL_DTA.DataContainer
Var = libSPELL_DTA.Var
'''
    elif name == 'spell/lang/constants.py':
        old = ('import spell.lib.adapter.data\n\n'
               'DataContainer = spell.lib.adapter.data.DataContainer\n'
               'Var           = spell.lib.adapter.data.Var\n')
        new = '''# Keep independent constants usable while native DTA is still a porting gate.
# Explicit requests for native types import the real library and fail clearly.
def __getattr__(name):
    if name in {'DataContainer', 'Var'}:
        from spell.lib.adapter import data
        return getattr(data, name)
    raise AttributeError(name)
'''
        assert text.count(old) == 1
        text = text.replace(old, new)
    elif name == 'spell/utils/grpc_utils.py':
        old = 'from concurrent.futures.thread import ThreadPoolExecutor, _worker,\\\n    _threads_queues'
        assert text.count(old) == 1
        text = text.replace(old, 'from concurrent.futures import ThreadPoolExecutor')
        start = text.index('    def _adjust_thread_count(self):')
        end = text.index('#==============================================================================', start)
        # Retain the existing class/constructor and use the stdlib worker pool.
        # CPython 3.13 changed its private worker signature; never copy it.
        text = text[:start] + '\n' + text[end:]
    elif name == 'spell/lib/adapter/databases/datasource.py':
        assert text.count('import urllib\n') == 1
        text = text.replace('import urllib\n', 'import urllib\nimport urllib.parse\n')
    elif name == 'spell/lib/drivermgr.py':
        text = text.replace('import traceback,sys\n', 'import traceback,sys,os\n')
        text = text.replace('        self.loaded = None\n        self.driverPackage = None',
                            '        self.loaded = None\n        self._added_paths = []\n        self.driverPackage = None')
        text = text.replace('                sys.path.append(lib)\n',
                            '                sys.path.append(lib)\n                self._added_paths.append(lib)\n')
        text = text.replace('            sys.path.append(self.driverPackage)\n',
                            '            sys.path.append(self.driverPackage)\n            self._added_paths.append(self.driverPackage)\n')
        start = text.index('    def cleanupCache(self):')
        end = text.index('    def createInterfaces(self):', start)
        text = text[:start] + '''    def cleanupCache(self):
        # Namespace modules may have __file__ = None. Match actual path ancestry,
        # not a substring, and remove only path entries this manager appended.
        if not self.driverPackage:
            return
        base = os.path.normcase(os.path.abspath(self.driverPackage))
        def belongs(value):
            if not isinstance(value, str):
                return False
            try:
                return os.path.commonpath([base, os.path.normcase(os.path.abspath(value))]) == base
            except (ValueError, OSError):
                return False
        for path in list(sys.path_importer_cache):
            if belongs(path):
                del sys.path_importer_cache[path]
        for moduleName, module in list(sys.modules.items()):
            if module is not None and belongs(vars(module).get('__file__')):
                del sys.modules[moduleName]
        for path in reversed(self._added_paths):
            for index in range(len(sys.path)-1, -1, -1):
                if sys.path[index] == path:
                    del sys.path[index]
                    break
        self._added_paths.clear()

    #==========================================================================
''' + text[end:]
    elif name == 'spell/utils/spell_service.py':
        text=text.replace('import os,time', 'import os,time\nfrom threading import RLock, current_thread')
        start=text.index('try:\n    global RegisterSpellService')
        end=text.index("STARTUP_NORMAL =",start)
        text=text[:start]+'''def SupportServices():
    try:
        from spell import runtime
    except ImportError:
        return False
    return callable(getattr(runtime, '_register_service', None))

def RegisterSpellService(service):
    if not SupportServices():
        raise RuntimeError('SPELL services require native context/service registration')
    from spell.runtime import _register_service as register
    return register(service)

'''+text[end:]
        start=text.index('    def _init_worker_pool(')
        end=text.index('class SpellService(',start)
        text=text[:start]+'''    def _init_worker_pool(self, name):
        self._pool = GRPCThreadPool(name,20)
        self._threads = []
        self._worker_lock = RLock()
        self._workers_closed = False

    def execute(self,targetFunction,*args,**kargs):
        with self._worker_lock:
            if self._workers_closed:
                raise RuntimeError('Service workers are stopped')
            return self._pool.submit(lambda: targetFunction(*args,**kargs))

    def repeatFunction(self,targetFunction,period,*args,**kargs):
        if period <= 0:
            raise ValueError('Service repeat period must be positive')
        with self._worker_lock:
            if self._workers_closed:
                raise RuntimeError('Service workers are stopped')
            worker = RepeatingThread(float(period),lambda: targetFunction(*args,**kargs))
            self._threads.append(worker)
            worker.start()
            return worker

    def _shutdown_workers(self):
        with self._worker_lock:
            self._workers_closed = True
            threads = tuple(self._threads)
            for worker in threads:
                worker.cancel()
        for worker in threads:
            if worker is not current_thread():
                worker.join()
        self._pool.shutdown(wait=True,cancel_futures=True)
        self._threads.clear()

'''+text[end:]
        text=text.replace('        RegisterSpellService(self)\n','')
        text=text.replace('        self.__impl = serviceImpl(*self.__attributes[0],**self.__attributes[1])','''        try:
            self.__impl = serviceImpl(*self.__attributes[0],**self.__attributes[1])
            RegisterSpellService(self)
        except BaseException:
            self._stop()
            raise''')
        text=text.replace('        if self.__ping != None:\n            self.__ping.cancel()','''        if self.__ping is not None:
            self.__ping.cancel()
            self.__ping.join()''')
        text=text.replace('    def _getStartCode(self):','''    def _stop(self):
        if self.__ping is not None:
            self.__ping.cancel()
            if self.__ping is not current_thread():
                self.__ping.join()
            self.__ping = None
        # The original decorator binds its worker helpers to itself. Services
        # inheriting AbstractSpellService may instead own their pool directly.
        for owner in (self, self.__impl):
            if owner is not None and hasattr(owner, '_worker_lock'):
                AbstractSpellService._shutdown_workers(owner)

    def _getStartCode(self):''')
        text=text.replace("        return self.__impl.__init__.__func__.__code__.co_filename.replace('.pyc','.py')",'''        initializer = self.__impl.__init__
        function = getattr(initializer, '__func__', initializer)
        return function.__code__.co_filename.replace('.pyc','.py')''')
    return text.encode('utf-8')
