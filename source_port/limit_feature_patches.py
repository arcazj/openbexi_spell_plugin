"""Checked limit profile extension after the accepted Group/Block composition."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES = {
    'openbexi_spell_dss/rpc.py': '816152c5a6ddbcb8509cea9ec10b94254be2c2b42e50026b23b04f7ffa47a179',
    'openbexi_dss_proxy/tm.py': '0f1488c410ba03869926be34acd1cbdf4e3cbc597646af0e01487ecc8b7e1203',
    'spell/lang/helpers/limhelper.py': '0285d403c30b2be282eaf01fc4966fc17e5c7508d8680a30be46367acd6f0922',
    'spell/lang/functions.py': 'b052dea1d9701117d703462dec427d5d120f4e99b6b77a2d3df2dab0e797ce11',
}


def replace(source, old, new):
    if source.count(old) != 1:raise ValueError('Limit source anchor differs: '+old[:90])
    return source.replace(old, new)


def replace_method(source, owner, method, following, body):
    start = source.index('    def '+method+'(', source.index('class '+owner+'('))
    end = source.index('    def '+following+'(', start)
    return source[:start]+body+'\n'+source[end:]


def helpers(source):
    source = replace_method(source, 'SetLimits_Helper', '_doPreOperation', '_doOperation', '''    def _doPreOperation(self, *args, **kargs):
        from openbexi_dss_proxy.limit_arguments import FIELDS, normalize
        if len(args) != 1:
            raise SyntaxException("Expected one TM parameter")
        param = args[0]
        if type(param) is not str and not isinstance(param, TmItemClass):
            raise SyntaxException("Expected a TM item or name")
        options = {key: self.getConfig(key) for key in FIELDS+('Definition', 'Limits', 'Expected', 'Select', 'Tolerance')
                   if self.hasConfig(key)}
        try:self.__result = normalize(options)
        except ValueError as error:raise SyntaxException(str(error)) from error
        self.__parameter = param
        if 'Definition' in self.__result:self.delConfig(Limits)
        self.setFailureInfo("TM", self.__result)
''')
    source = replace_method(source, 'AdjustLimits_Helper', '_doPreOperation', '_doOperation', '''    def _doPreOperation(self, *args, **kargs):
        if len(args) != 1 or type(args[0]) is not list or not args[0]:
            raise SyntaxException("Expected a nonempty TM verification list")
        self.__verifyList = args[0]
        self.setFailureInfo("TM", args[0])
''')
    source = replace_method(source, 'AdjustLimits_Helper', '_doOperation', '_doRepeat', '''    def _doOperation(self, *args, **kargs):
        result = REGISTRY['TM'].adjustLimits(self.__verifyList, self.getConfig(), eq)
        return [False, result, NOTIF_STATUS_OK if result else NOTIF_STATUS_FL, ""]
''')
    start = source.index('class LoadLimits_Helper(')
    source = source[:start]+replace(source[start:], 'if len(args)==0:', 'if len(args)!=1:')
    source += '''

class AlarmControl_Helper(WrapperHelper):
    def __init__(self, enabled):
        WrapperHelper.__init__(self, "TM")
        self.enabled = enabled
        self._opName = "Enable alarm" if enabled else "Disable alarm"
        self.setConfig({OnFailure:SKIP|REPEAT|CANCEL|ABORT})

    def _doPreOperation(self, *args, **kargs):
        if len(args) != 1 or (type(args[0]) is not str and not isinstance(args[0], TmItemClass)):
            raise SyntaxException("Expected one TM item or name")
        self.parameter = args[0]
        self.setFailureInfo("TM", self.parameter)

    def _doOperation(self, *args, **kargs):
        result = REGISTRY['TM'].setAlarm(self.parameter, self.enabled, self.getConfig())
        return [False, result, NOTIF_STATUS_OK if result else NOTIF_STATUS_FL, ""]

    def _doRepeat(self):return [True, None]
    def _doSkip(self):return [False, True]
    def _doCancel(self):return [False, False]
'''
    return source


def proxy(source):
    source = replace(source, 'from .limit_support import set_limits', 'from .limit_profile import set_limits')
    source = replace(source, 'from .limit_support import get_limits', 'from .limit_profile import get_limits')
    source = replace(source,
        "validate_settings(config, ('Definition','Limits','Select','Type','LoRed','LoYel','HiYel','HiRed','Midpoint'))",
        "from .limit_arguments import FIELDS\n        validate_settings(config, FIELDS+('Definition','Limits','Select','Type'))")
    anchor = '    def _restoreNormalLimits(self,config=None):'
    source = replace(source, anchor, '''    def setAlarm(self, parameter, enabled, config):
        from .limit_profile import alarm
        validate_settings(config)
        item = self[parameter] if type(parameter) is str else parameter
        return alarm(item, enabled, config)

    def _loadLimits(self, uri, config):
        from .limit_profile import load
        validate_settings(config)
        return load(uri, config)

    def adjustLimits(self, conditions, config, equality):
        from .limit_profile import adjust
        validate_settings(config, ('Select',))
        return adjust(conditions, config, equality)

'''+anchor)
    return source


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Limit feature preimage differs: '+name)
    source = raw.decode('utf-8')
    if name == 'spell/lang/helpers/limhelper.py':source = helpers(source)
    elif name == 'openbexi_dss_proxy/tm.py':source = proxy(source)
    elif name == 'spell/lang/functions.py':
        for verb, enabled in (('enable', True), ('disable', False)):
            source = replace(source, '    Display("Cannot '+verb+' alarm: not implemented", Severity = WARNING )\n    return True',
                '    from .helpers.limhelper import AlarmControl_Helper\n'
                '    helper = AlarmControl_Helper('+repr(enabled)+')\n'
                '    helper.configure(*args, **kargs)\n'
                '    return helper.execute(*args, **kargs)')
    else:source = dispatcher(source)
    result = source.encode('utf-8')
    compile(result, name, 'exec')
    return result


def dispatcher(source):
    anchor = "        if family == 'TM' and method in {'SetLimits','GetLimits','IsAlarmed','InjectItem','RestoreNormalLimits'}:"
    if source.count(anchor) != 1:raise ValueError('Limit dispatch anchor differs')
    source = source.replace(anchor, """        if family == 'TM' and method in {'SetLimits', 'GetLimits', 'IsAlarmed', 'RestoreNormalLimits'}:
            from .limits import Limits
            def acquire(name):
                check()
                return self.prepare('TM', 'RefreshItem', p.TmItemValue(item=p.TmItemDesc(mnemonic=name)),
                                    identity, request_id, check)()
            return Limits(self, acquire).prepare(method, request, check)
"""+anchor)
    return source


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    outputs = {name: apply(name, (site/name).read_bytes()) for name in PREIMAGES}
    report = {}
    for name, output in outputs.items():
        for label, content in (('original', (site/name).read_bytes()), ('patched', output)):
            path = evidence/label/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (site/name).write_bytes(output)
        report[name] = dict(preimage_sha256=PREIMAGES[name], sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    import sys
    apply_tree(sys.argv[1], sys.argv[2])
