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
    'spell/lib/adapter/utctime.py': '3ba8116f625a261d0f692899e7b4c2f292859cc5c242f10573ccfdd807b76ded',
    'spell/lang/helpers/basehelper.py': '8cbca48bb966b427455acc74177448c73cbb1e31898181a923331afe99b8cd81',
    'spell/lang/helpers/genhelper.py': '0f5c3bc2fce17e231df4e0474297a9c7fb2faa5fc556e043ca9f64ba70372c86',
    'spell/config/contexts.py': '1e271d7a7cd6ba180dfbd606e6bf65d45845343506e486ccfb5c620ca90523b1',
}


def apply(name, original):
    if name not in PREIMAGES:
        return original
    if hashlib.sha256(original).hexdigest() != PREIMAGES[name]:
        raise ValueError('Upstream patch preimage changed: ' + name)
    text = original.decode('utf-8')
    if name == 'spell/lang/helpers/basehelper.py':
        text = text.replace('        self._customException = self.getConfig(HandleError)\n', '')
        anchor = '        # Standard exception handling\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, '        self._validateCommonConfig(self.getConfig(), supplied)\n\n' + anchor)
        anchor = '    def configure(self, *args, **kargs ):\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, anchor + '''        supplied = {}
        for value in args:
            if type(value) is dict:
                supplied.update(value)
        supplied.update(kargs.get('config', {}))
        supplied.update({key:value for key,value in kargs.items() if key != 'config'})
''')
        anchor = '    def cleanup(self, *args, **kargs ):\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, '''    def _validateCommonConfig(self, config, supplied=None):
        # LRM pp.28-31,116-117: validate policy before an operation has effects.
        for modifier in (HandleError, PromptFailure, PromptUser, Notify):
            if modifier in config and type(config[modifier]) is not bool:
                raise SyntaxException("Expected boolean modifier: " + modifier)
        allowed = ABORT|SKIP|CANCEL|REPEAT|RECHECK|RESEND|NOACTION|RESUME|HANDLE
        for modifier in (OnFailure, OnTrue, OnFalse):
            if modifier not in config:
                continue
            value = config[modifier]
            if type(value) is not int or value <= 0 or value & ~allowed:
                raise SyntaxException("Invalid action: " + modifier)
            if modifier != OnFailure and value & HANDLE:
                raise SyntaxException("HANDLE requires OnFailure")
            interactive = config.get(PromptFailure if modifier == OnFailure else PromptUser, True)
            explicit = supplied is None or modifier in supplied
            if modifier == OnFailure and value == NOACTION and interactive and explicit:
                raise SyntaxException("OnFailure=NOACTION requires PromptFailure=False")
            if not interactive and explicit:
                if value & (value - 1):
                    raise SyntaxException("Automatic action must have one value: " + modifier)
                if value == HANDLE:
                    raise SyntaxException("HANDLE requires PromptFailure=True")
            elif interactive and value & NOACTION and value != NOACTION:
                raise SyntaxException("NOACTION cannot be a prompt option")
        if FailureCode in config and type(config[FailureCode]) is not int:
            raise SyntaxException("FailureCode must be an integer")

    #===========================================================================
    def cleanup(self, *args, **kargs ):
''')
        text = text.replace('        shouldPrompt = self._getExceptionFlag(exception)',
                            '        shouldPrompt = True if options is not None else self._getExceptionFlag(exception)')
        anchor = '        doPrompt = self.getConfig(PromptUser)\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, anchor + '''        if not doPrompt and cfg & (cfg - 1):
            raise SyntaxException("Automatic result action must have one value")
''')
        anchor = '            cfgAction = self.getConfig(OnFailure)\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, anchor + '''            if cfgAction & (cfgAction - 1):
                raise SyntaxException("Automatic failure action must have one value")
''')
        anchor = '        # If there are no options defined\n'
        assert text.count(anchor) == 1
        text = text.replace(anchor, '''        # NOACTION is an automatic failure policy, not an interactive option.
        # A failed operation has no result to manufacture into success.
        if options is None and self.getConfig(OnFailure) == NOACTION:
            return ACTION_NOACTION

''' + anchor)
        text = text.replace('            result = [False,True]\n        elif action == ACTION_CANCEL:',
                            '            result = [False,None]\n        elif action == ACTION_CANCEL:')
        text = text.replace('            self.setConfig({OnFailure:ABORT})',
                            '            self.addConfig(OnFailure,ABORT)')
        text = text.replace('        self.__actionStrings = self._ACTIONS',
                            '        self.__actionStrings = self._ACTIONS.copy()')
    elif name == 'spell/config/contexts.py':
        old = '        self.__functionConfig.get(functionName)[modifier] = value'
        assert text.count(old) == 1
        text = text.replace(old, '        self.__functionConfig.setdefault(functionName, {})[modifier] = value')
    elif name == 'spell/lang/helpers/genhelper.py':
        start = text.index('class ChangeLanguageConfig_Helper(')
        end = text.index('class GetLanguageConfig_Helper(', start)
        block = text[start:end]
        old = '''        elif inspect.isfunction(self.__configurable):
            self.__isInterface = False'''
        assert block.count(old) == 1
        block = block.replace(old, '''        elif inspect.isfunction(self.__configurable):
            from spell.lang import functions
            if getattr(functions, self.__configurable.__name__, None) is not self.__configurable:
                raise SyntaxError("Expected an original SPELL language function")
            self.__isInterface = False''')
        anchor = '    #===========================================================================\n    def _doOperation(self, *args, **kargs ):\n'
        assert block.count(anchor) == 1
        block = block.replace(anchor, '''        # Validate the whole change before modifying the procedure defaults.
        from spell.lang import modifiers
        for name in kargs:
            if getattr(modifiers, name, None) != name:
                raise SyntaxException("Unknown modifier: " + repr(name))
        self._validateCommonConfig(kargs)

''' + anchor)
        text = text[:start] + block + text[end:]
    elif name == 'spell/lib/adapter/utctime.py':
        text = text.replace('import datetime,time\n', 'import calendar,datetime,re,time\n')
        old = '        return time.mktime(val.timetuple())'
        assert text.count(old) == 1
        text = text.replace(old, '        return calendar.timegm(val.utctimetuple()) + val.microsecond / 1000000.0')
        old = '''    def __rsub__(self, timestamp):
        return TIME(self.value() - self.__translate(timestamp).value())'''
        assert text.count(old) == 1
        text = text.replace(old, '''    def __rsub__(self, timestamp):
        return TIME(self.__translate(timestamp).value() - self.value())''')
        old = '''    def cnv(self, timestamp):

        mydt = datetime.datetime(1,1,1)'''
        assert text.count(old) == 1
        text = text.replace(old, r'''    def cnv(self, timestamp):

        # LRM 2.4.4 pp.32-33: signed seconds and optional relative seconds.
        # Parse the documented grammar rather than evaluating its components.
        if isinstance(timestamp, str) and timestamp.startswith(('+', '-')):
            if re.fullmatch(r'[+-]\d+(?:\.\d{1,6})?', timestamp):
                return datetime.timedelta(seconds=float(timestamp))
            relative = re.fullmatch(r'([+-])(?:(\d+) )?(\d+):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?', timestamp)
            if relative is None:
                return None
            sign, days, hours, minutes, seconds, micros = relative.groups()
            if int(minutes) > 59 or int(seconds or '0') > 59:
                return None
            value = datetime.timedelta(days=int(days or '0'), hours=int(hours),
                minutes=int(minutes), seconds=int(seconds or '0'),
                microseconds=int((micros or '0').ljust(6, '0')))
            return -value if sign == '-' else value

        mydt = datetime.datetime(1,1,1)''')
    elif name == 'spell/lib/adapter/data.py':
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
