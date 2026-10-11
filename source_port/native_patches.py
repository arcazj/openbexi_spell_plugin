"""Hash-checked CPython 3.13 native port. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
import re
from pathlib import Path

PREIMAGES = {
    'lib/SPELL_UTIL/src/SPELLtime.C': '00eee7607928a34af2ba69a687b290566687155a80d7299d9a4a1f432f248585',
    'lib/SPELL_CTX/src/SPELLservice.C': '8edac0867351e1c6354c1ee39bbd329b891a690dd371616ffe3cc69a37912a01',
    'include/SPELL_CTX/SPELLserviceManager.H': '64cf81cd4c38302faf5fb9313602b8d4c77ded11bf5bca9f5d6b62618a443f98',
    'include/SPELL_CTX/SPELLservice.H': '0a4163783dd1cf876fb6d044c53de499e6d3aa93cc4d0bd0957b1248d933c258',
    'lib/SPELL_IPC/src/SPELLipcChannel.C': '6129e3bf83729b19d8550d9d4dac761f8fb18f4a7c681e70c8e37005c5bba215',
    'include/SPELL_IPC/SPELLipcChannel.H': '0732dc2720f944d2dfff371e67598122f50f4615c4705866479c45358e8e925b',
    'lib/SPELL_IPC/src/SPELLipcServerInterfaceSingle.C': '79d7f62a6b70982cc8a5e64f1517d082464d1271b1e8851c13538435c42d0284',
    'include/SPELL_IPC/SPELLipcServerInterfaceSingle.H': '54d5d913f116f49ecf8b1304b4ca2a5192f8e8a12888736609099d33bc8cc179',
    'include/SPELL_IPC/SPELLipcClientInterface.H': '8b9c11c92e264867c406c6ddbcc98bf2300698fdd7cf69b921e7fb08344af00a',
    'include/SPELL_IPC/SPELLipcTrash.H': '81c6959c6aa793b67ff1b60e62e00dfb8853d1bc9da117381534f544ad138b91',
    'lib/SPELL_EXC/src/SPELLchildManager.C': 'd026e3b74f02cf5a588c44e3e6d1012f378feabb0300b657ca5167c8b2bb6169',
    'include/SPELL_EXC/SPELLchildManager.H': 'c98c691cb249a9c609eeefd897b60ea38921148c96a80ead9313c2a50dd1b97d',
    'include/SPELL_EXC/SPELLcontroller.H': '13ef9f674eba595c54f28de89aef816f758c8049be67f1257c6f5457a2acbb37',
    'lib/SPELL_CTX/src/SPELLexecutorManager.C': '0ed8194465b987c76b2113fb64512190430b6dd64cc02893966bd5817b818312',
    'lib/SPELL_CTX/src/SPELLexecutor.C': '63db5c0e063e08ad4fea0bcd4c66efb53b205beb6218a226c6ab7573ae677d32',
    'include/SPELL_CTX/SPELLexecutorManager.H': '1dda9ee8dd638986f6a11d4d97a0a169119e1676d4783f8a9db29f9e0301cb7b',
    'include/SPELL_CTX/SPELLexecutor.H': '6dab907284243d68a44ea10d10e12c6290e91f0eeb773632a9818db6c35972fb',
    'lib/SPELL_EXC/src/SPELLvariableManager.C': '29161553e78c161ff5c85d527b9dbd1e6767ba22860ce508f1ddd7ea26c17c8b',
    'include/SPELL_EXC/SPELLvariableMonitor.H': '38330bc82263583ad697ca25a3cbe89e2b38416010ad5961433fbe09ea5fbb16',
    'lib/SPELL_EXC/src/SPELLcontroller.C': 'e056206fb6d16a725bdc8d7b9a031cd4b6ba3ef3104e37f5c370ab581d521bb8',
    'lib/SPELL_CIF/src/SPELLasRun.C': 'b7b43f0cc3b6704af6a20f75be2dbd17481786388e880b32eb27fc4d057fcea3',
    'include/SPELL_CIF/SPELLasRun.H': 'bf636883d4a9b3a338e8b2d75eacb3abb74a126f3a39fc1c9367edcf526caaef',
    'include/SPELL_PRD/SPELLpyService.H': '94e3dcf3ce42bd6b504f4ee69b8e518773a060a399042b3da93f03ad28fc5c23',
    'include/SPELL_CIF/SPELLcifStartupInfo.H': '76362db765deeeae57f4940084535a1e5aa66d5a1b5669df16fe8dbcd3c803d4',
    'include/SPELL_CIF/SPELLcif.H': 'a3243ecab708477e8451e9231a5a1b4c28f4eafb0b1507a8ce2a2128916596cf',
    'lib/SPELL_CIF/src/SPELLcif.C': '203bf8e38160e92770791a90bdf2339cb774ecdaf6bbe77ec3037f5162e3560f',
    'lib/SPELL_CTX/src/SPELLserviceManager.C': 'c84e2bd832b6d5fd2a1b212694876fbeabcfaa98a6536b81800fa68dd540af90',
    'src/service/src/SPELLserviceMain.C': '5323a5d5ecdc6718a973dca8581bc46f9f251451c42c69207842022b4dbdb2f6',
    'lib/SPELL_EXC/src/SPELLserviceInterpreter.C': '0d7291373b9afc3b55655b90d771f00c87b1db42889e1a4d9a62a161fcdfb7e5',
    'include/SPELL_EXC/SPELLserviceInterpreter.H': 'e7f00e852f5c40bac74b4bc9efe82e177ce42018872ec5e505d865733600b3ef',
    'include/SPELL_IPC/SPELLipcServerInterface.H': '9f7eee06aaed4bde66623442391417dbe695823bc3c251ced02f3ba89c052af2',
    'lib/SPELL_IPC/src/SPELLipcServerInterface.C': '9712a92efe49d1bc3b02281606e8ef36d336b5cbe54fc33e9c4a414022a893b5',
    'lib/SPELL_IPC/src/SPELLipcIncoming.C': 'f8c18b685d1b952d4fb40bf5da81bbe30a4f1b343b3a54491842f011eff01b3c',
    'src/listener/src/SPELLlistenerMain.C': 'dec6280cca0ddb40251bbb534529af176274607476524f223a6e49370d588998',
    'lib/SPELL_IPC/src/SPELLipcTrash.C': '70a45d45652dd3b00bd51ce839d1cf2cef1b4db0149f17ec04e19426800c437b',
    'lib/SPELL_PRD/src/SPELLpyService.C': '6a5e9a79e22f31396c2203c7982b896b7023099c2702ce6ef2da91b7fc54fc68',
    'lib/SPELL_PRD/src/SPELLserviceWatchdogPython.C': '599edcbc388652f7f710660835858cf5dd4b5febc2f2245b15a46ba0af471ff9',
    'lib/SPELL_PRD/src/SPELLserviceRegisterPython.C': 'd24afdd1b36ce6d46151e681e8d853ce25de3966c464483493b5b4e153694145',
    'include/SPELL_CIFS/SPELLserverCif.H': 'ad3ce9638c238300604e0408cacfa387a561cf0c9c662583b6bcccee5fffdeba',
    'lib/SPELL_CIFS/src/SPELLserverCif.C': '9d37476b9f14a41945f2a5afee1e5b6d3f659bd3fd8236aff4f0d2a2106005a7',
    'src/executor/src/SPELLexecutorMain.C': 'b7d2263cdfc850fa7e2778906cc5893d3d0f2ba9d5e1aee991ea8cd01c61b111',
    'lib/SPELL_IPC/src/SPELLipcClientInterface.C': '2a2cfe1befef43d44229e1438e7cd5925aa0699a8c2d18b501376b980e9334a5',
    'lib/SPELL_IPC/src/SPELLsocket.C': '3720c025525a5b63fac8bdf6a0f0cf8c87ab585836b77db3085ddd6990a39cb8',
    'include/SPELL_IPC/SPELLsocket.H': 'bdf0a1643dc8fc77dd83a47009c3b3a60fa95ea8efca1563fa4e6cfe24942350',
    'lib/SPELL_CTX/src/SPELLcontext.C': 'cf4576a8a95c543cddd53b8cb4f136a53e0114c1fc5bf3ebd6e39b1c0ff9129c',
    'lib/SPELL_LST/src/SPELLlistenerContext.C': 'ce7c6b3e16847584ad0a6e0e677ed5f9c16de4b560c3a29f7b08f1e8d72c1e2f',
    'include/SPELL_PRC/SPELLprocess.H': 'd2484b06554a45f808340963a253df43e96ad78dbc152a053bccd0ee533c2a17',
    'include/SPELL_PRC/SPELLprocessManager.H': 'f2b9306b10592069c71a43efd01d2ae85f722a4e3d96dc51a3826164deb9fcf9',
    'lib/SPELL_PRC/src/SPELLprocess.C': '2fb4528c3cdc56ca20cfb21a6567dc621690b032b0076f09fe66e276743de6f1',
    'lib/SPELL_PRC/src/SPELLprocessManager.C': 'aa6ae8d3d2f9d5f804a74eabe5af07d8001ba419ad4e30e158c07f47f2e716db',
    'include/SPELL_SYN/SPELLtimer.H': '152943d761837f7312aa38064f7db9ddbc99ec6e5d392bc44ea58bcd84aff23d',
    'lib/SPELL_CIF/src/SPELLcifHelper.C': '7316ec1d703e4aa883adbb07301ea7428b3fb111460bf4cfe3b3e7c974018a24',
    'lib/SPELL_CIFC/src/SPELLautomaticCif.C': 'ea34aa30832faf2ae3f8c605abb281afa45eb4d241b19c7604a5c090a10b625e',
    'lib/SPELL_SYN/src/SPELLtimer.C': '80dd7599733c64b5f2769a37c2c8ea1451afc23f12c195545031d67f87cfc0a8',
    'lib/SPELL_EXC/src/SPELLscheduler.C': '2d00d9b9d5e5296799582e7937873639ca4400eb204fec174317b29c36bdd50a',
    'include/SPELL_PRD/SPELLprocedureManager.H': '699e72c66c8e8242a0575f9c032b215314d7c88b744d6108cdcb4fa9f60ed997',
    'lib/SPELL_PRD/src/SPELLprocedureManager.C': '69c8b97d451a40a99ea86d7248eb82c3a0c8608af60924a0f80e45523c1c72b5',
    'lib/SPELL_EXC/src/SPELLexecutorConfiguration.C': '78bb96d7d61cdb5eb016a0416f45b878ecd9347ea5b23a89487dffd8fcbd6474',
    'include/SPELL_EXC/SPELLinterpreter.H': '2eaf1ea5f53624fab196e62fc6668c26f8a00d5397b3b5051a4fa2b14a137006',
    'lib/SPELL_EXC/src/SPELLinterpreter.C': '3dd0a455669237924726637ca4b25ae524acfaf10d577b18a7c36258ad3f1256',
    'src/executorcmd/src/SPELLexecutorMain.C': 'cc29574b068d1135bf216914e85f690d6945c59b28b88d1b14988d4bb4b26d2d',
    'lib/SPELL_WRP/src/SPELLregistry.C': '0823e4ff6607903845d6333cdb6f975bb36f1c8c78e31dd3400665686b599e2d',
    'lib/SPELL_EXC/src/SPELLexecutorPython.C': '89abec69514d3022550ef4f39264895a5fc9df18bff82b7a7ff535389b66e33e',
    'lib/SPELL_EXC/src/SPELLstepPython.C': 'e34081213079d413548ed25c614072318f5d899b353223d9f37517319069cb7c',
    'lib/SPELL_EXC/src/SPELLgotoPython.C': 'af1d3dfa62eef6117ede5e1a51c13cd4a09d4f8b28f84fd6560d28630a1a9fe7',
    'lib/SPELL_CIF/src/SPELLcifPython.C': 'c5ea8a8bccd44c9701f74117dbaa4baa4efaa068ef9618ff539fcac7a6333cb0',
    'include/SPELL_WS/SPELLwarmstart.H': 'c073afc45bc4feccb0a7501aea58c4deec51499c0517db0c689df5f4d653a280',
    'include/SPELL_WS/SPELLwsDynamicData.H': '0ead809531f5542c91e95131956305e27a39d02c2845af76ce0daa9d6507c2c5',
    'lib/SPELL_WS/src/SPELLwsDynamicData.C': '466ea5544f5e2cfeed11040defe72dc66c0db0606575a685912d130f0e1bc53f',
    'include/SPELL_WS/SPELLwsStaticData.H': '6cb9e5a8b85166e83fcaa3b2b3ba3e2931a1c7d70a72ee9252d6e108385d9525',
    'lib/SPELL_WS/src/SPELLwsStaticData.C': 'b5530d8a3dbdff7f3e3e5545a59272ec733f8b9aecb632e263aae19a07c8031a',
    'include/SPELL_WS/SPELLwsFrame.H': '583b07b7b4dd82a3c360527576d0bc1f129b3a19a7c5e2e598bca9b5e1d6034b',
    'lib/SPELL_WS/src/SPELLwsFrame.C': 'da9bc5ea2c6037ec2719cd0f3c4929eb975aa018b92a5dd4d4c7d5c63876d2e6',
    'include/SPELL_EXC/SPELLframeManager.H': '4c265b25b8e311bef3ff2bf08374e023160346c97d27883b086882daac3602b5',
    'include/SPELL_EXC/SPELLexecutor.H': '6671885f2423ea99d080e0f06049a91b0fee3352e7e0469b19467f53ecb8cb01',
    'include/SPELL_DTA/SPELLdtaContainer.H': 'bf2de9f9ef83507f86acde77e8c5d896009bca6b1c616c809dcab9e53f6e7a07',
    'include/SPELL_DTA/SPELLdtaVariable.H': 'dfbc1e34ae04f9713bf80f4b2edef8fb5c09e678795046a1ce58f88789d915f0',
    'lib/SPELL_DTA/src/SPELLdtaContainer.C': 'c0dbe9140ac7934f0e6af0688ec44ca49962e36204977b0d53ea78f656197050',
    'lib/SPELL_DTA/src/SPELLdtaContainerObjectMethods.C': 'd8acdcadff6d1881cd61fd4447c8fa43b19292eb1c9b077c613856e55bbdb6b6',
    'lib/SPELL_DTA/src/SPELLdtaModule.C': '41fc9488d7f4831eb1d60a94ddf068fbd96698003ee24e37e22a0376dd728e0f',
    'lib/SPELL_DTA/src/SPELLdtaVariable.C': '1fc250c12a0e5dce65471c8a9fa4b4a31fc377bb77e8dce8aeddeebb0b60913e',
    'lib/SPELL_DTA/src/SPELLdtaVariableObjectMethods.C': 'a1de382ba85e164f02f3b9a7ef9d59d9fd8c6aa447a56601056b94a3c2fe63ac',
    'lib/SPELL_WRP/src/SPELLpyValue.C': 'd641a196503bb44286030f27fcc66b39b42159e71e60c9aa8f7a20ccd6407eba',
    'lib/SPELL_EXC/src/SPELLframeManager.C': 'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
    'include/SPELL_WS/SPELLwsWarmStartImpl.H': '70692486c7a89222fa682ee0aee82a19e7d43a97381aedfd5623e1370a12b7cf',
    'lib/SPELL_WS/src/SPELLwsWarmStartImpl.C': 'b0bb02ac4636ae398ed57fcfed3d4ef2cb35b5f19f03c1b8300c2fe5b1e163f6',
    'lib/SPELL_EXC/src/SPELLexecutionModel.C': '45545e623c76fcf2d0817ed761f262a835479e08adeaf0658bb3f956b94c5038',
    'lib/SPELL_EXC/src/SPELLexecutorImpl.C': '3a891afdf5e0dbcd75f97db263e3c30311c597872e434fc91b6c993683b2b0df',
    'lib/SPELL_EXC/src/SPELLserviceImpl.C': '9e56ddfa666429777f37ab7bedb76de9a539145050123096554339bb1ea40382',
    'lib/SPELL_EXC/src/SPELLbytecode.C': 'ab9e4c3accad70a664cfbfff43da74686777213f0ec98cd85250f73df04fcd60',
    'include/SPELL_EXC/SPELLbytecode.H': 'ade8253aa4387aa5f0fa633a31ec6e1689eb88fc960fb64ece274427141eeb18',
    'lib/SPELL_EXC/src/SPELLvariableMonitor.C': '7162c7a9abab73cb9b9e20bc34f8e32185d6a4ab728e12d80989bf64bcb27aa7',
    'lib/SPELL_WS/src/SPELLwsStorage.C': '85fff1d7e917ce5913daaf99ecb385362a2f5323d49d7d41de8125b1e13ee34f',
    'lib/SPELL_EXC/src/SPELLgoto.C': '6ff696df62c225f7adb17d12dd0e8581988eb0bf327105c45d07ebbacae4560f',
    'lib/SPELL_EXC/src/SPELLastAnalyzer.C': '5f5ab545c54e182c5b4b74feaae7ee386bb5d926f85b066dfe38b5ad73de59af',
    'include/SPELL_EXC/SPELLastAnalyzer.H': '7ad2a805f8b499b3438c8b2c848b5cc36129388bd0027bc7c9e749f417dba1f1',
    'lib/SPELL_EXC/src/SPELLlnotab.C': '5c7598a5444bde5cde810a8335081f8b683579e874e6958ab678999c8e17c5f3',
    'include/SPELL_EXC/SPELLlnotab.H': '9ed4e9b200153a3c52d29ba9c0d2f2add53f1001acd244ff55cad25d78b188a4',
    'include/SPELL_UTIL/SPELLpythonMonitors.H': 'ff0f9af10116d360b85ea19b3479da94a4df856c95e2c0067c35fbe871caff19',
    'lib/SPELL_UTIL/src/SPELLpythonHelper.C': '2610cab71f4d339ff33ffaa90486deaa060cf3060435a433b8f888c72824d837',
    'lib/SPELL_UTIL/src/SPELLutils.C': 'ee16758649173ca2c838545f43d6d44dfbd5264bc25bb1fa2257b4ffdd509d70',
    'lib/SPELL_UTIL/src/SPELLerror.C': 'e95b2787936e7ee0b56d5e956e6ba07db138dbab13abfec2dc07ef6a859f3f93',
    'include/SPELL_UTIL/SPELLpythonHelper.H': '4e28c64ccdfeb24c9e855339b2d3b4d6f89caa03216ec9a4730189a635ff139a',
    'lib/SPELL_UTIL/src/SPELLlogPython.C': '2d98e6606c3c9e7a8eada2bd56fe9784547209a9d48644eac24b055234883be4',
}
ROOT = Path(__file__).resolve().parent / 'native'


def section(text, start, end, body):
    assert text.count(start) == 1, start
    a = text.index(start)
    b = text.index(end, a)
    assert a < b
    return text[:a] + body + '\n' + text[b:]


def body(name):
    return (ROOT / name).read_text(encoding='utf-8')


def binding(text, prefix, registry=None, counts=None):
    text = text.replace('#include "structmember.h"', '#include "structmember.h"\n#include "SPELL_UTIL/SPELLbinding313.H"')
    spec = f'''static PyType_Slot {prefix}_Slots[] = {{
    {{Py_tp_new, reinterpret_cast<void*>(PyType_GenericNew)}},
    {{Py_tp_methods, reinterpret_cast<void*>({prefix}_Methods)}},
    {{0,nullptr}}
}};
static PyType_Spec {prefix}_Spec = {{"spell.runtime.{prefix}",sizeof(Py{prefix}Object),0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_IMMUTABLETYPE,{prefix}_Slots}};'''
    if not registry:
        count = 2 if prefix == 'Step' else 1
        spec = spec.replace('{0,nullptr}',f'{{Py_tp_call,reinterpret_cast<void*>(SPELLbinding313::keywords<{prefix}_Call,{count},{count}>)}},\n    {{0,nullptr}}')
    text, changed = re.subn(r'static PyTypeObject '+prefix+r'_Type =\s*\{.*?\n\};',lambda _:spec,text,count=1,flags=re.S)
    assert changed == 1
    export = {'Executor':'_executor','ClientIF':'_cif'}.get(prefix,prefix)
    register = (f'SPELLregistry::instance().set(object.get(),"{registry}");\n    SPELLpythonHelper::instance().install(object.get(),"{export}");' if registry
                else f'SPELLpythonHelper::instance().install(object.get(),"{prefix}");')
    install = f'''void {prefix}_Install()
{{
    SPELLpython313::Owned object(SPELLbinding313::instance(&{prefix}_Spec));
    {register}
}}'''
    text, changed = re.subn(r'void '+prefix+r'_Install\(\)\s*\{.*?\n\}',lambda _:install,text,count=1,flags=re.S)
    assert changed == 1
    if counts is not None:
        # The original method names and method bodies stay authoritative.
        def entry(match):
            name, method, flags, rest = match.groups()
            minimum, maximum = counts[name] if name in counts else (0,0)
            if name == 'startPrompt': flags = 'METH_VARARGS'
            wrapper = 'keywords' if 'METH_KEYWORDS' in flags else 'call'
            return f'{{"{name}",(PyCFunction)SPELLbinding313::{wrapper}<{method},{minimum},{maximum}>,{flags},{rest}'
        text, count = re.subn(r'\{"(\w+)"\s*,\s*(?:\(PyCFunction\))?('+prefix+r'_\w+)\s*,\s*(METH_\w+(?:\s*\|\s*METH_\w+)?)\s*,([^\n]+)',entry,text)
        assert count == (29 if prefix == 'Executor' else 14), count
    marker=f'static PyMethodDef {prefix}_Methods[] =\n{{'
    assert marker in text
    reduction=f'''static PyObject* {prefix}_Reduce(PyObject*,PyObject*) {{ return PyUnicode_FromString("{export}"); }}
'''
    text=text.replace(marker,reduction+marker+f'\n    {{"__reduce__",{prefix}_Reduce,METH_NOARGS,"Reference the current runtime binding"}},')
    return text


def apply(name, original):
    if name not in PREIMAGES:
        return original
    if hashlib.sha256(original).hexdigest() != PREIMAGES[name]:
        raise ValueError('Native preimage differs: ' + name)
    text = original.decode('utf-8')
    if name.endswith('SPELLipcIncoming.C'):
        text='#include <memory>\n'+text
        for kind in ('Message','Request'):
            start=text.index('void SPELLipcIncoming'+kind+'::run()')
            end=text.find('\n//=============================================================================',start)
            if end<0: end=len(text)
            part=text[start:end]
            part=part.replace('setStarted();','').replace('finish();','')
            part=part.replace('::run()\n{', '''::run()
{
    setStarted();
    auto complete=[this](SPELLipcIncomingBase*) { finish(); };
    std::unique_ptr<SPELLipcIncomingBase,decltype(complete)> completion(this,complete);''')
            text=text[:start]+part+text[end:]
        text=text.replace('bool SPELLipcIncomingBase::isFinished()\n{', 'bool SPELLipcIncomingBase::isFinished()\n{\n    SPELLmonitor lock(m_dataLock);')
    elif name.endswith('SPELLipcServerInterface.H'):
        text='#include <atomic>\n'+text
        text,count=re.subn(r'bool\s+m_connected;', 'std::atomic_bool m_connected;',text)
        assert count==1
    elif name.endswith('SPELLipcServerInterface.C'):
        start=text.index('        if (clientSocket == NULL && !m_clientKeysToRemove.empty())')
        end=text.index('        if ((!disconnected)&&clientSocket != NULL)',start)
        text=text[:start]+'''        if (clientSocket == nullptr) {
            std::vector<int> pending;
            { SPELLmonitor lock(m_clientCleanupLock); pending.swap(m_clientKeysToRemove); }
            for (int key : pending) removeClientInternal(key);
        }
'''+text[end:]
        text=section(text,'void SPELLipcServerInterface::removeClientInternal(',
            'void SPELLipcServerInterface::removeAllClients()','''void SPELLipcServerInterface::removeClientInternal(int key)
{
    SPELLipcChannel* channel=nullptr;
    {
        SPELLmonitor lock(m_clientLock);
        auto found=m_clients.find(key);
        if (found==m_clients.end() || !found->second) return;
        channel=found->second;
        // Keep the map node stable for incoming processors holding its address,
        // but revoke access to the channel before releasing ownership.
        found->second=nullptr;
        auto used=std::find(m_usedClientKeys.begin(),m_usedClientKeys.end(),key);
        if (used!=m_usedClientKeys.end()) m_usedClientKeys.erase(used);
    }
    channel->disconnect();
    delete channel;
    LOG_INFO(NAME + "Removed client " + ISTR(key));
}

''')
        text=section(text,'void SPELLipcServerInterface::removeAllClients()',
            'void SPELLipcServerInterface::disconnect()','''void SPELLipcServerInterface::removeAllClients()
{
    std::vector<int> keys;
    { SPELLmonitor lock(m_clientLock);
      for (const auto& entry : m_clients) if (entry.second) keys.push_back(entry.first); }
    for (int key : keys) removeClientInternal(key);
    { SPELLmonitor lock(m_clientCleanupLock); m_clientKeysToRemove.clear(); }
}

''')
        text=text.replace('    DEBUG(NAME + "Removing clients");\n    removeAllClients();\n    DEBUG(NAME + "Server interface wait to disconnect...");\n    join();','''    // The accept loop also removes disconnected channels. Join it before
    // final cleanup so only one owner can disconnect/delete each channel.
    DEBUG(NAME + "Server interface wait to disconnect...");
    join();
    DEBUG(NAME + "Removing clients");
    removeAllClients();''')
    elif name.endswith('SPELLipcTrash.C'):
        text=text.replace('    m_trashFinishEvent.wait();', '    m_trashFinishEvent.wait();\n    { SPELLmonitor lock(m_dataLock); for (auto* p : m_messages) LOG_INFO(NAME + \"Draining \" + p->getProcessingId()); }')
        text=text.replace('    m_trashWorking = false;', '    { SPELLmonitor lock(m_dataLock); m_trashWorking = false; }')
        start=text.index('void SPELLipcTrash::clearData()')
        text=text[:start]+'''void SPELLipcTrash::clearData()
{
    SPELLmonitor lock(m_dataLock);
    for (auto it=m_messages.begin(); it!=m_messages.end();) {
        auto* processor=*it;
        if (!processor || (processor->isStarted() && !processor->wait(25))) {
            if (processor) { processor->join(); delete processor; }
            it=m_messages.erase(it);
        } else ++it;
    }
}
'''
    elif name == 'src/listener/src/SPELLlistenerMain.C':
        text=text.replace('SPELLevent s_finishEvent;', 'sigset_t shutdownSignals;')
        start=text.index('void signal_handler(int signum)')
        end=text.index('// MAIN PROGRAM',start)
        text=text[:start]+'''// Block orderly termination before starting any workers. The owner thread
// consumes it with sigwait; no mutex, allocation, logging or shutdown runs
// from an asynchronous signal handler. Fault signals retain their defaults.
void setupSignals()
{
    sigemptyset(&shutdownSignals);
    for (int value : {SIGINT,SIGTERM,SIGHUP,SIGQUIT}) sigaddset(&shutdownSignals,value);
    if (pthread_sigmask(SIG_BLOCK,&shutdownSignals,nullptr)!=0)
        throw std::runtime_error("Cannot block listener shutdown signals");
}

//============================================================================
'''+text[end:]
        text=text.replace('#include <backward.hpp>', '#include <backward.hpp>')
        text='#include <stdexcept>\n#include <pthread.h>\n'+text
        text=text.replace('    SPELLlistener::get().start(configFile);\n\n    setupSignals();\n\n    s_finishEvent.clear();\n    s_finishEvent.wait();','''    setupSignals();
    SPELLlistener::get().start(configFile);
    int signal=0;
    if (sigwait(&shutdownSignals,&signal)!=0) return 1;''')
    elif name.endswith('SPELLserviceRegisterPython.C'):
        text=text[:text.index('// FILES TO INCLUDE')]+body('service_registration.cpp')
    elif name.endswith('SPELLserviceWatchdogPython.C'):
        text=text[:text.index('// FILES TO INCLUDE')]+body('service_watchdog.cpp')
    elif name.endswith('SPELLpyService.H'):
        text=text.replace('SPELLpyService(PyObject* serviceImpl);', 'SPELLpyService(PyObject* serviceImpl, const std::string& name, const std::string& basePath, const std::string& mainFile);')
    elif name.endswith('SPELLpyService.C'):
        text=text.replace('SPELLpyService::SPELLpyService(PyObject* serviceImpl)', 'SPELLpyService::SPELLpyService(PyObject* serviceImpl, const std::string& name, const std::string& basePath, const std::string& mainFile)')
        start=text.index('    SPELLpyHandle pyServiceName =')
        end=text.index('    m_service = serviceImpl;',start)
        text=text[:start]+'    m_name=name;\n    m_basePath=basePath;\n    m_mainServiceFile=mainFile;\n'+text[end:]
        # Source construction can throw; own the Python reference only after it.
        text=text.replace('    Py_IncRef(serviceImpl);', '')
        text=text.replace('    m_source = SPELLprocedureSourceCode(this->getMainServiceFile());', '    m_source = SPELLprocedureSourceCode(this->getMainServiceFile());\n    Py_INCREF(m_service);')
        text=text.replace('#include "SPELL_PRD/SPELLpyService.H"','#include "SPELL_PRD/SPELLpyService.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text=text.replace('    Py_DecRef(m_service);', '    SPELLsafePythonOperations ops("Release service");\n    SPELLpyHandle stopped=PyObject_CallMethod(m_service,"_stop",nullptr);\n    if (!stopped.get()) PyErr_WriteUnraisable(m_service);\n    Py_DECREF(m_service);')
        old='    SPELLpyHandle newCommand = PyObject_CallMethod(m_service,(char*)"_start", (char*)"()",NULL);\n    SPELLpythonHelper::instance().checkError();'
        new='''    SPELLpyHandle newCommand = PyObject_CallMethod(m_service,(char*)"_start", (char*)"()",NULL);
    // The original controller stores termination separately from Python's
    // exception indicator. Preserve it for serviceImpl's execution result.
    auto& error=SPELLerror::instance();
    if (!newCommand.get() && (error.isExecutionAborted() || error.isExecutionTerminated()))
        PyErr_Clear();
    else SPELLpythonHelper::instance().checkError();'''
        assert old in text
        text=text.replace(old,new)
        text=text.replace('PyObject* callbackObj = SpellServiceWatchdog_Create(callback);','SPELLpyHandle callbackObj = SpellServiceWatchdog_Create(callback);\n    SPELLpythonHelper::instance().checkError();')
        text=text.replace('"(O)", callbackObj,NULL','"(O)", callbackObj.get(),NULL')
    elif name.endswith('SPELLtimer.H'):
        text=text.replace('#define __SPELL_TIMER_H__','#define __SPELL_TIMER_H__\n#include <atomic>')
        text=text.replace('bool           m_counting;','bool           m_counting;\n    std::atomic_bool m_shuttingDown{false};')
    elif name.endswith('SPELLtimer.C'):
        text=text.replace('    m_counting = false;\n    m_stopEvent.set();','    m_shuttingDown.store(true);\n    setCounting(false);\n    m_stopEvent.set();')
        text=text.replace('while(isCounting())','while(!m_shuttingDown.load() && isCounting())')
        text=text.replace('        if (callTimerCallback())','        if (m_shuttingDown.load()) return;\n        if (callTimerCallback())')
        text = text.replace('    m_stopEvent.set();\n}', '    m_stopEvent.set();\n    join(); // the worker must leave before its mutexes/events are destroyed\n}',1)
    elif name.endswith('SPELLsocket.H'):
        text=text.replace('#define __SPELL_SOCKETS_H__','#define __SPELL_SOCKETS_H__\n#include <atomic>')
        text=text.replace('int m_socketFd;', 'std::atomic<int> m_socketFd;')
        text=text.replace('bool m_connected;', 'std::atomic_bool m_connected;')
    elif name.endswith('SPELLsocket.C'):
        text=text.replace('SPELLsocket::~SPELLsocket()\n{','SPELLsocket::~SPELLsocket()\n{\n    close();')
        text=text.replace('if (errno > 0)', 'if (numWritten < 0)')
        for method,how,return_type in [('shutdownRead','SHUT_RD','void'),('shutdownWrite','SHUT_WR','void'),('shutdown','SHUT_RDWR','int'),('close',None,'void')]:
            content='    m_connected=false;\n    const int fd=m_socketFd.exchange(-1);\n'
            content+='    if (fd<0) return'+(' 0' if return_type=='int' else '')+';\n'
            if how: content+='    ::shutdown(fd,'+how+');\n'
            content+='    '+('return ' if return_type=='int' else '')+'::close(fd);\n'
            text,count=re.subn(return_type+r' SPELLsocket::'+method+r'\(\)\s*\{.*?\n\}',lambda _:return_type+' SPELLsocket::'+method+'()\n{\n'+content+'}',text,count=1,flags=re.S)
            assert count==1,method
        start=text.index('SPELLsocket* SPELLsocket::acceptClient(')
        end=text.index('SPELLsocket* SPELLsocket::connect(',start)
        part=text[start:end].replace('m_socketFd','socketFd')
        part=part.replace('    // Master file descriptor list','    const int socketFd=m_socketFd.load();\n    if (socketFd<0) { *disconnected=true; return nullptr; }\n    // Master file descriptor list')
        text=text[:start]+part+text[end:]
    elif name.endswith('SPELLipcClientInterface.C'):
        text=section(text,'SPELLipcClientInterface::~SPELLipcClientInterface()', 'void SPELLipcClientInterface::connect(', '''SPELLipcClientInterface::~SPELLipcClientInterface()
{
    disconnect();
}
//=============================================================================
''')
        text=text.replace('    m_socket = SPELLsocket::connect( m_serverHost, m_serverPort );', '''    if (isConnected()) throw SPELLipcError("Client already connected");
    if (m_channel) { delete m_channel; m_channel=nullptr; }
    else delete m_socket;
    m_socket=nullptr;
    m_socket = SPELLsocket::connect( m_serverHost, m_serverPort );''')
        text=section(text,'void SPELLipcClientInterface::disconnect()', 'void SPELLipcClientInterface::connectionLost(', '''void SPELLipcClientInterface::disconnect()
{
    // Connection loss also requires cleanup: the flag is not ownership.
    m_connected=false;
    cancelOutgoingRequests();
    cancelIncomingRequests();
    m_mailbox.shutdown();
    if (m_channel) {
        DEBUG(NAME + "Cleanup: disconnect channel");
        m_channel->disconnect();
        DEBUG(NAME + "Cleanup: destroy channel");
        delete m_channel; // channel owns and destroys its socket
        m_channel=nullptr;
    } else delete m_socket; // connect failed before a channel was installed
    m_socket=nullptr;
    DEBUG(NAME + "Cleanup: stop incoming processors");
    m_trash.shutdown();
    DEBUG(NAME + "Cleanup: join request collector");
    m_trash.join();
    DEBUG(NAME + "Cleanup complete");
}
//=============================================================================
''')
    elif name.endswith('SPELLchildManager.H'):
        text=text.replace('void openChildProcedure(', 'void prepareChild(const std::string& instanceId);\n        void openChildProcedure(')
    elif name.endswith('SPELLchildManager.C'):
        start=text.index('void SPELLchildManager::openChildProcedure(')
        end=text.index('void SPELLchildManager::closeChildProcedure()',start)
        part=text[start:end]
        part=part.replace('    SPELLmonitor m(m_lock);\n\n    m_childStart.clear();',
            '    { SPELLmonitor lock(m_lock); m_childStart.clear(); }')
        part=part.replace('    std::string subProcInstance = cif.openSubprocedure( suitableProc, callingLine, args, automatic, blocking, visible );', '''    std::string subProcInstance;
    try { subProcInstance=cif.openSubprocedure(suitableProc,callingLine,args,automatic,blocking,visible); }
    catch (...) { m_childStart.set(); throw; }''')
        part=part.replace('        m_childProc = subProcInstance;\n        m_childAlive = true;\n        m_childStatus = STATUS_LOADED;',
            '        // Identity is installed before launch; preserve newer child notifications.')
        text=text[:start]+part+text[end:]
        text+='''
void SPELLchildManager::prepareChild(const std::string& instanceId)
{
    SPELLmonitor lock(m_lock);
    m_childProc=instanceId;
    m_childAlive=true;
    m_childStatus=STATUS_UNINIT;
    m_childError.clear();
    m_childErrorReason.clear();
    m_childStart.set();
}
'''
    elif name.endswith('SPELLcontroller.H'):
        text = text.replace('#define __SPELL_CONTROLLER_H__', '#define __SPELL_CONTROLLER_H__\n#include <mutex>\n#include <memory>')
        text = text.replace('SPELLevent           m_execLock;', '''SPELLevent           m_execLock;
        // Only the active CPython trace thread may change frame.f_lineno.
        std::mutex m_traceMutex;
        std::unique_ptr<ExecutorCommand> m_traceCommand;
        SPELLevent m_traceCommandDone;
        bool m_traceWaiting = false;
        bool m_traceContinue = false;''')
    elif name.endswith('SPELLcontroller.C'):
        text=text.replace('if (!m_error && !m_finished)', 'if (!m_error)')
        text=text.replace('        executeCommand(cmd);', '''        bool deferred=false;
        if (cmd.id==CMD_SKIP || cmd.id==CMD_GOTO) {
            std::lock_guard<std::mutex> guard(m_traceMutex);
            if (m_traceWaiting) {
                m_traceCommandDone.clear();
                m_traceCommand.reset(new ExecutorCommand(cmd));
                m_execLock.set();
                deferred=true;
            }
        }
        // Keep the original mailbox serialization and command completion.
        if (deferred) m_traceCommandDone.wait();
        else executeCommand(cmd);''',1)
        text=section(text,'void SPELLcontroller::doWait()',
                     'void SPELLcontroller::callbackEventLine(',body('controller_wait.cpp'))
    elif name.endswith('SPELLscheduler.C'):
        text = text.replace('#include "SPELL_EXC/SPELLscheduler.H"','#include "SPELL_EXC/SPELLscheduler.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = text.replace('    m_pyTM = NULL;\n    delete m_timer;', '''    delete m_timer; // joins before Python references are released
    SPELLpython313::GIL gil;
    Py_CLEAR(m_pyTM);''')
        text = text.replace('        Py_INCREF(m_pyTM);','')
    elif name.endswith('SPELLcifHelper.C'):
        text = text.replace('    \tpromptResult = def.expected[STRI(result)];', '''        int index=-1;
        auto conversion=std::from_chars(result.data(),result.data()+result.size(),index);
        if (conversion.ec!=std::errc() || conversion.ptr!=result.data()+result.size() ||
            index<0 || static_cast<size_t>(index)>=def.expected.size())
            THROW_EXCEPTION("Invalid prompt answer","Answer is not a valid option index",SPELL_ERROR_EXECUTION);
        promptResult=def.expected[index];''')
        text = '#include <charconv>\n'+text
    elif name.endswith('SPELLserverCif.H'):
        text=text.replace('#define __SPELL_SERVER_CIF_H__','#define __SPELL_SERVER_CIF_H__\n#include <atomic>')
        text=text.replace('bool m_ready;','std::atomic_bool m_ready;')
    elif name.endswith('SPELLserverCif.C'):
        text=text.replace('    subprocId = response.get(MessageField::FIELD_INSTANCE_ID);',
            '    subprocId = response.get(MessageField::FIELD_INSTANCE_ID);\n    if (response.isVoid() || response.getType()==MSG_TYPE_ERROR || subprocId.empty())\n        THROW_EXCEPTION("Unable to start subprocedure", "Context did not allocate a child identifier", SPELL_ERROR_EXECUTION);\n    SPELLexecutor::instance().getChildManager().prepareChild(subprocId);')
        # Close admission on the receiving worker, without transferring mutex
        # ownership to the interpreter thread. Existing requests drain first.
        text=text.replace('    \tm_ipcLock.lock();\n    \tsetClosing();', '        { SPELLmonitor guard(m_ipcLock); setClosing(); }')
        text=text.replace('    m_ipcLock.unlock();', '')
        for method, following in [('sendGUIRequest','sendGUIMessage'),('sendCTXRequest','sendCTXMessage')]:
            start=text.index('SPELLipcMessage SPELLserverCif::'+method+'(')
            end=text.index('void SPELLserverCif::'+following+'(',start)
            part=text[start:end].replace('if (m_ready)', 'if (m_ready && !isClosing())')
            text=text[:start]+part+text[end:]
        # A detached controlling client cannot acknowledge its final status.
        # Closing cancels notification retries; it does not forge an ACK.
        text,count=re.subn(r'while\s*\(!waitAcknowledge\(msg\)\);',
            'while (!isClosing() && !waitAcknowledge(msg));',text)
        assert count==4
        text=text.replace('if (!m_ready) return false;', 'if (!m_ready || isClosing()) return false;')
        text=text.replace('void SPELLserverCif::specificCleanup( bool force )\n{',
            'void SPELLserverCif::specificCleanup( bool force )\n{\n    { SPELLmonitor guard(m_ipcLock); setClosing(); m_ready=false; }')
    elif name.endswith('SPELLautomaticCif.C'):
        text = text.replace('rawAnswer = SPELLcifHelper::getRawAnswer( answer, def );', '''rawAnswer = SPELLcifHelper::getRawAnswer( answer, def );
    if (rawAnswer.empty() && !def.options.empty())
        THROW_EXCEPTION("Invalid prompt answer","Answer does not match an expected option",SPELL_ERROR_EXECUTION);''')
    elif name.endswith('SPELLprocedureManager.H'):
        text = text.replace('void setup(const std::string& ctxName);','void setup(const std::string& ctxName);\n    void registerScript(const std::string& file);\n    void cleanupServices();')
    elif name.endswith('SPELLprocedureManager.C'):
        text=text.replace('#include "SPELL_WRP/SPELLpyHandle.H"','#include "SPELL_WRP/SPELLpyHandle.H"\n#include <memory>')
        text=text.replace('#include <memory>', '#include <memory>\n#include <stdexcept>\n#include "SPELL_UTIL/SPELLpython313.H"')
        text=text.replace('SPELLpyService* serviceModel = new SPELLpyService(serviceImpl);', '''auto metadata=[&](const char* key) {
        SPELLpython313::Owned value(PyObject_CallMethod(serviceImpl,key,nullptr));
        if (!value.get()) throw std::runtime_error("Cannot read service metadata");
        if (!PyUnicode_Check(value.get()) || PyUnicode_GetLength(value.get())==0) {
            PyErr_SetString(PyExc_TypeError,"Service metadata must be nonempty strings");
            throw std::runtime_error("Invalid service metadata");
        }
        Py_ssize_t size=0;
        const char* bytes=PyUnicode_AsUTF8AndSize(value.get(),&size);
        if (!bytes) throw std::runtime_error("Cannot encode service metadata");
        std::string result(bytes,size);
        if (result.find('\\0')!=std::string::npos) {
            PyErr_SetString(PyExc_ValueError,"Service metadata cannot contain NUL");
            throw std::runtime_error("Invalid service metadata");
        }
        return result;
    };
    const std::string serviceName=metadata("getName");
    if (m_serviceModels.count(serviceName))
        THROW_EXCEPTION("Cannot register service", "Duplicate name", SPELL_ERROR_PROCEDURES);
    const std::string basePath=metadata("getBasePath");
    const std::string mainFile=metadata("getMainFile");
    std::unique_ptr<SPELLpyService> serviceModel(new SPELLpyService(serviceImpl,serviceName,basePath,mainFile));''')
        text=text.replace('m_serviceModels[serviceModel->getName()] = serviceModel;', 'const std::string name=serviceModel->getName();\n    m_serviceModels.emplace(name,serviceModel.release());')
        text=text.replace('PyObject* result = SPELLpythonHelper::instance().callFunction("spell.utils.spell_service","SupportServices",NULL);\n    Py_IncRef(result);', 'SPELLpyHandle result = SPELLpythonHelper::instance().callFunction("spell.utils.spell_service","SupportServices",NULL);')
        text=text.replace('if (result == Py_False)', 'if (result.get() == Py_False)')
        text=text.replace('catch (SPELLcoreException& e)\n            {\n\n            }', 'catch (SPELLcoreException& e)\n            {\n                LOG_ERROR("Cannot import service " + serviceModuleName + ": " + e.what());\n                throw;\n            }')
        text += '\nvoid SPELLprocedureManager::cleanupServices()\n{\n    ServiceModelMap models;\n    models.swap(m_serviceModels);\n    for (auto& entry : models) delete entry.second;\n}\n'
        text += '''
// Explicit -f execution admits an ordinary Python script without the indexed
// procedure's spacecraft header. Keep the original model and source reader.
void SPELLprocedureManager::registerScript(const std::string& file)
{
    SPELLmonitor lock(m_lock);
    SPELLprocedure* model=new SPELLprocedure(SPELLutils::basePath(file),file);
    auto previous=m_procModels.find(file);
    if (previous!=m_procModels.end()) delete previous->second;
    m_procModels[file]=model;
    m_filenameToId[file]=file;
    m_idToFilename[file]=file;
    m_idToName[file]=model->getName().empty() ? file : model->getName();
}
'''
    elif name.endswith('SPELLexecutorConfiguration.C'):
        text = text.replace('m_parentProcId = -1;', 'm_parentProcId = ""; // no parent; never a non-UTF-8 sentinel byte')
    elif name == 'include/SPELL_CTX/SPELLexecutor.H':
        text='#include <atomic>\n'+text
        text=text.replace('    void run();', '    void run();\n    void stop() { m_stopping.store(true); }')
        text=text.replace('    SPELLexecutor& m_exec;', '    std::atomic_bool m_stopping{false};\n    SPELLexecutor& m_exec;')
        for type_,field in [('bool','m_reconnecting'),('bool','m_loggedIn'),('SPELLprocessStatus','m_processStatus')]:
            text,count=re.subn(r'\b'+type_+r'\s+'+field+r';', 'std::atomic<'+type_+'> '+field+';',text)
            assert count==1,(name,field)
        text=text.replace('virtual bool isLoggedIn()', 'virtual void reconnectCompleted(bool success);\n        virtual bool isLoggedIn()')
        text=text.replace('LoginMonitor( SPELLexecutor& exec )','LoginMonitor( SPELLexecutor& exec, unsigned int timeoutMsec=120000 )')
        text=text.replace('m_exec( exec )','m_exec( exec ), m_timeoutMsec(timeoutMsec)')
        text=text.replace('    SPELLexecutor& m_exec;','    SPELLexecutor& m_exec;\n    unsigned int m_timeoutMsec;')
    elif name == 'include/SPELL_CTX/SPELLservice.H':
        text=text.replace('void start();','void start();\n        void reconnectCompleted(bool success) override;')
    elif name == 'lib/SPELL_CTX/src/SPELLservice.C':
        text += "\nvoid SPELLservice::reconnectCompleted(bool success)\n{\n    if (success) SPELLserviceManager::instance().callback_serviceReconnected(m_model.getInstanceId());\n    else SPELLserviceManager::instance().callback_serviceNotReconnected(m_model.getInstanceId());\n}\n"
    elif name == 'include/SPELL_CTX/SPELLserviceManager.H':
        text=text.replace('friend class ServiceLoginMonitor;', 'friend class ServiceLoginMonitor;\n        friend class SPELLservice;')
        text=text.replace('ServiceMap m_pendingLogin;', 'ServiceMap m_pendingLogin;\n        ServiceMap m_retiredLogin;')
        text=text.replace('ServiceList getServiceList();', 'ServiceList getServiceList();\n        bool isActiveOrPending(const std::string& serviceId);')

    elif name == 'include/SPELL_CTX/SPELLexecutorManager.H':
        text=text.replace('friend class LoginMonitor;', 'friend class LoginMonitor;\n        friend class SPELLexecutor;')
        text=text.replace('ExecutorMap m_pendingLogin;', 'ExecutorMap m_pendingLogin;\n        ExecutorMap m_retiredLogin;')
    elif name == 'lib/SPELL_CTX/src/SPELLexecutor.C':
        text='#include <chrono>\n'+text
        text=section(text,'void LoginMonitor::run()', 'SPELLexecutor::SPELLexecutor( const', '''void LoginMonitor::run()
{
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(m_timeoutMsec);
    while (!m_stopping.load()) {
        if (m_exec.isLoggedIn()) { m_exec.reconnectCompleted(true); return; }
        if (std::chrono::steady_clock::now()>=deadline) { m_exec.reconnectCompleted(false); return; }
        usleep(30000);
    }
}
//=============================================================================
''')
        text += "\nvoid SPELLexecutor::reconnectCompleted(bool success)\n{\n    if (success) SPELLexecutorManager::instance().callback_executorReconnected(m_model.getInstanceId());\n    else SPELLexecutorManager::instance().callback_executorNotReconnected(m_model.getInstanceId());\n}\n"
        text=text.replace('\tm_loggedIn = true;\n\tm_model.setStatus(STATUS_UNINIT);','\tm_model.setStatus(STATUS_UNINIT);')
        text=text.replace('\tm_executorLoggedInEvent.set();','\tm_loggedIn = true; // publish only after metadata and process attachment\n\tm_executorLoggedInEvent.set();')
        text=text.replace('void SPELLexecutor::waitFinish()\n{\n\tif', 'void SPELLexecutor::waitFinish()\n{\n    m_processStoppedEvent.clear();\n\tif')
        text=text.replace('\t\tm_processStoppedEvent.clear();\n','')
        text=section(text,'bool SPELLexecutor::waitStatus(', 'SPELLexecutorStatus SPELLexecutor::getStatus()', body('context_wait_status.cpp'))
        text=text.replace('\t\t\tm_loginMonitor->join();', '\t\t\tm_loginMonitor->stop();\n            m_loginMonitor->join();\n            delete m_loginMonitor;\n            m_loginMonitor=nullptr;')
    elif name == 'lib/SPELL_CTX/src/SPELLexecutorManager.C':
        text=section(text,'void SPELLexecutorManager::cleanup()', 'void SPELLexecutorManager::startExecutor(','''void SPELLexecutorManager::cleanup()
{
    ExecutorMap pending,retired;
    { SPELLmonitor lock(m_lock);
      pending.swap(m_pendingLogin); retired.swap(m_retiredLogin); }
    // Destruction cancels and joins monitors outside the manager lock. A
    // monitor finishing concurrently sees an empty pending map and returns.
    for (auto& entry : pending) delete entry.second;
    for (auto& entry : retired) delete entry.second;
    delete m_persisTable; m_persisTable=nullptr;
}

''')
        start=text.index('void SPELLexecutorManager::callback_executorNotReconnected(')
        end=text.index('void SPELLexecutorManager::recoverExecutor(',start)
        part=text[start:end].replace('\t\tdelete it->second;', '// The callback runs on this executor\'s own monitor. Retire it\n        // for owner-thread cleanup instead of destroying a running worker.\n        m_retiredLogin.emplace(instanceId,it->second);')
        text=text[:start]+part+text[end:]
    elif name == 'lib/SPELL_CTX/src/SPELLcontext.C':
        start=text.index('        SPELLserviceManager::ServiceList runningServices =')
        end=text.index('        SPELLcontext::instance().openService(serviceId);',start)
        text=text[:start]+"        if (SPELLserviceManager::instance().isActiveOrPending(serviceId)) return;\n"+text[end:]
        text=text.replace('\tSPELLexecutorManager::instance().cleanup();\n\tm_clientIPC.cleanup();\n\tSPELLexecutorManager::instance().killAll();', '\tm_clientIPC.cleanup();\n    SPELLexecutorManager::instance().killAll();\n    SPELLexecutorManager::instance().cleanup();')
        text=text.replace('\tSPELLclientManager::instance().removeAllClients();', '''    { SPELLpython313::GIL gil; SPELLprocedureManager::instance().cleanupServices(); }
    for (const auto& id : SPELLserviceManager::instance().getServiceList())
        SPELLserviceManager::instance().closeService(id);
    SPELLserviceManager::instance().cleanup();
    SPELLclientManager::instance().removeAllClients();''')
        text = text.replace('#include "SPELL_CTX/SPELLcontext.H"', '#include "SPELL_CTX/SPELLcontext.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text,count = re.subn(r'\tif \(SPELLconfiguration::instance\(\).getContextParameter\(USE_DRIVER_TIME\) == "true"\)\n\t\{\n\t\tSPELLdriverManager::instance\(\).cleanup\(true\);\n\t\}', '', text)
        assert count==1
        text = text.replace('SPELLpythonHelper::instance().acquireGIL();', '''{ SPELLpython313::GIL gil;
      SPELLdriverManager::instance().cleanup(true); }
    // finalize restores the owner's saved thread state itself.''')
        text = text.replace('m_eventFinish.clear();\n\tm_eventFinish.wait();', 'm_eventFinish.wait();')
        text = text.replace('void SPELLcontext::start( const SPELLcontextConfiguration& config )\n{',
            'void SPELLcontext::start( const SPELLcontextConfiguration& config )\n{\n    m_eventFinish.clear(); // arm before publishing IPC readiness')
    elif name == 'include/SPELL_PRC/SPELLprocess.H':
        text = text.replace('// FILES TO INCLUDE', '#include <memory>\n#include <atomic>\n#include <mutex>\n// FILES TO INCLUDE',1)
        text = text.replace('class SPELLprocess : public SPELLthread', 'class SPELLprocess : public SPELLthread, public std::enable_shared_from_this<SPELLprocess>')
        assert 'enable_shared_from_this<SPELLprocess>' in text
        text = text.replace('void run();', 'void run();\n        void join();\n        bool isClosing() const { return m_aboutToClose; }')
        for type_,field in [('pid_t','m_processPID'),('int','m_retValue'),('int','m_status'),
                ('SPELLprocessStatus','m_statusCode'),('bool','m_killIt'),('bool','m_aboutToClose')]:
            text,count = re.subn(r'\b'+type_+r'\s+'+field+r';', 'std::atomic<'+type_+'> '+field+';',text)
            assert count==1,(name,field)
        text = text.replace('bool                    m_notChild;', 'std::mutex m_waitLock;\n        bool m_notChild;')
    elif name == 'lib/SPELL_PRC/src/SPELLprocess.C':
        # Listener workers inherit its sigwait mask; each child must receive
        # its own termination signals normally after exec.
        text=text.replace('    else if (pid == 0)\n    {', '''    else if (pid == 0)
    {
        sigset_t termination;
        sigemptyset(&termination);
        for (int value : {SIGINT,SIGTERM,SIGHUP,SIGQUIT}) sigaddset(&termination,value);
        if (sigprocmask(SIG_UNBLOCK,&termination,nullptr)!=0) _exit(127);''')
        start=text.index('        if (execl("/bin/bash"')
        end=text.index('    return pid;',start)
        text=text[:start]+'''        execl("/bin/bash", "bash", "-c", command.c_str(), nullptr);
        // Only async-signal-safe operations between fork and exec/_exit.
        const char failure[]="SPELL child exec failed\\n";
        write(STDERR_FILENO,failure,sizeof(failure)-1);
        _exit(127);
    }
'''+text[end:]
        text = text.replace('// DEFINES ', 'static thread_local SPELLprocess* currentProcess=nullptr;\n// DEFINES ',1)
        if 'static thread_local SPELLprocess*' not in text:
            text = text.replace('//=============================================================================', 'static thread_local SPELLprocess* currentProcess=nullptr;\n//=============================================================================',1)
        text = text.replace('    this->join();', '    if (currentProcess==this) pthread_detach(pthread_self());\n    else this->join();')
        start=text.index('void SPELLprocess::run()')
        end=text.index('void SPELLprocess::kill()',start)
        part=text[start:end]
        part=part.replace('void SPELLprocess::run()\n{', '''void SPELLprocess::run()
{
    struct Current {
        SPELLprocess* previous=currentProcess;
        Current(SPELLprocess* value) { currentProcess=value; }
        ~Current() { currentProcess=previous; }
    } current(this);
    // A listener may remove/restart this identifier from this very callback.
    // Keep the original monitor alive until its native run method returns.
    auto keepAlive=shared_from_this();
    int observedStatus=0;''')
        part=part.replace('&m_status','&observedStatus')
        # A nonblocking wait here could reap a fast child, leaving the blocking
        # wait below to misreport ECHILD as an unexpected process death.
        part=section(part,'\t\tDEBUG("[PRC] Waiting PID");',
            '\t\tDEBUG("[PRC] The process has started, starting check");','')
        part=part.replace('m_processPID = popen( m_command );',
            'm_processPID = popen( m_command );\n            if (m_processPID<=0) THROW_EXCEPTION("Cannot start child", "fork failed", SPELL_ERROR_PROCESS);')
        part=part.replace('int result = waitpid( m_processPID, &observedStatus, WUNTRACED );', 'int result;\n            do { result=waitpid(m_processPID,&observedStatus,WUNTRACED); } while (result<0 && errno==EINTR);\n            m_status=observedStatus;')
        text=text[:start]+part+text[end:]
        text = section(text,'int SPELLprocess::wait()', 'pid_t SPELLprocess::popen(', '''void SPELLprocess::join()
{
    if (currentProcess==this) return;
    std::lock_guard<std::mutex> lock(m_waitLock);
    SPELLthread::join();
}
int SPELLprocess::wait()
{
    join();
    return m_retValue;
}
//=============================================================================
''')
    elif name == 'include/SPELL_PRC/SPELLprocessManager.H':
        text = text.replace('// FILES TO INCLUDE', '#include <memory>\n// FILES TO INCLUDE',1)
        text = text.replace('std::map<std::string,SPELLprocess*>', 'std::map<std::string,std::shared_ptr<SPELLprocess>>')
        text = text.replace('bool checkProcessExist(', 'bool isClosingProcess(const std::string& identifier);\n        bool checkProcessExist(')
    elif name == 'lib/SPELL_PRC/src/SPELLprocessManager.C':
        for parameter in ('command','pid'):
            text=text.replace('SPELLprocess* process = new SPELLprocess(identifier,'+parameter+',this);',
                'if (m_processes.count(identifier)) THROW_EXCEPTION("Cannot start process", "Duplicate identifier", SPELL_ERROR_PROCESS);\n    auto process=std::make_shared<SPELLprocess>(identifier,'+parameter+',this);')
        text=text.replace('    process->start();\n','')
        text=text.replace('    m_processes.insert( std::make_pair( identifier, process ));',
            '    m_processes.emplace(identifier,process);\n    try { process->start(); } catch (...) { m_processes.erase(identifier); throw; }')
        text=section(text,'int SPELLprocessManager::waitProcess(', 'SPELLprocessStatus SPELLprocessManager::getProcessStatus(', '''int SPELLprocessManager::waitProcess(const std::string& identifier)
{
    std::shared_ptr<SPELLprocess> process;
    { SPELLmonitor lock(m_lock);
      auto found=m_processes.find(identifier);
      if (found==m_processes.end()) THROW_EXCEPTION("Cannot wait for process", "Not found", SPELL_ERROR_PROCESS);
      process=found->second; }
    return process->wait();
}
bool SPELLprocessManager::isClosingProcess(const std::string& identifier)
{
    SPELLmonitor lock(m_lock);
    auto found=m_processes.find(identifier);
    return found==m_processes.end() || found->second->isClosing();
}
//=============================================================================
''')
        text=section(text,'void SPELLprocessManager::clearProcess(', 'void SPELLprocessManager::addListener(', '''void SPELLprocessManager::clearProcess(const std::string& identifier)
{
    std::shared_ptr<SPELLprocess> process;
    { SPELLmonitor lock(m_lock);
      auto found=m_processes.find(identifier);
      if (found==m_processes.end()) return;
      process=found->second;
      m_processes.erase(found); }
    process->join();
}
//=============================================================================
''')
        text=text.replace('mit = listeners.find(identifier);\n    if (mit != m_listeners.end())', 'mit = listeners.find(identifier);\n    if (mit != listeners.end())')
        text=text.replace('SPELLprocessListenersMap listeners = m_listeners;', 'SPELLprocessListenersMap listeners;\n    { SPELLmonitor lock(m_lock); listeners=m_listeners; }')
    elif name == 'lib/SPELL_LST/src/SPELLlistenerContext.C':
        text=text.replace('    closemsg.setType( MSG_TYPE_ONEWAY );', '    SPELLprocessManager::instance().aboutToCloseProcess("CTX_" + name);\n    closemsg.setType( MSG_TYPE_ONEWAY );')
        for method in ('processKilled','processFailed'):
            marker='void SPELLlistenerContext::'+method+'( const std::string identifier )\n{'
            assert marker in text
            text=text.replace(marker,marker+'\n    if (SPELLprocessManager::instance().isClosingProcess(identifier)) return;')
        text=text.replace('\n    usleep(10000000);', '\n    usleep(10000000);\n    if (SPELLprocessManager::instance().isClosingProcess(identifier)) return;')
        text=re.sub(r'(\s*)(SPELLprocessManager::instance\(\).killProcess\(\s*(.*?)\s*\);)',
            r'\1SPELLprocessManager::instance().aboutToCloseProcess(\3);\1\2',text)
    elif name.endswith('SPELLasRun.H'):
        text=text.replace('const std::string& procId );', 'const std::string& procId, bool service=false );',1)
    elif name.endswith('SPELLasRun.C'):
        text=text.replace('const std::string& procId )', 'const std::string& procId, bool service )',1)
        text=text.replace('    // Dump procedure header to the AsRun file\n    try', '    // Service identity is authoritative; services are not procedure models.\n    if (service) m_file << "# SERVICE: " << procId << std::endl;\n    else\n    // Dump procedure header to the AsRun file\n    try',1)
    elif name.endswith('SPELLcifStartupInfo.H'):
        text=text.replace('procId = info.procId;', 'procId = info.procId;\n        service = info.service;')
        text=text.replace('procId = info->procId;', 'procId = info->procId;\n        service = info->service;')
        text=text.replace('std::string procId;', 'bool service=false;\n    std::string procId;')
    elif name.endswith('SPELLcif.H'):
        text=text.replace('std::string m_procId;', 'bool m_service=false;\n        std::string m_procId;')
    elif name.endswith('SPELLcif.C'):
        text=text.replace('new SPELLasRun( ctx, m_timeId, m_procId )','new SPELLasRun( ctx, m_timeId, m_procId, m_service )')
        text=text.replace('m_procId = info.procId;', 'm_procId = info.procId;\n    m_service = info.service;')
        text=text.replace('if (m_procId.find("#") == std::string::npos)', 'if (!m_service && m_procId.find("#") == std::string::npos)')
    elif name.endswith('SPELLserviceInterpreter.H'):
        text=text.replace('void mainLoop();','void mainLoop();\n        void shutdown();\n        int exitCode() const { return m_exitCode; }')
        text=text.replace('SPELLcontrollerIF*       m_controller;', 'bool m_controllerStarted=false;\n        SPELLcontrollerIF*       m_controller;')
        text=text.replace('SPELLinterpreterConfig   m_config;', 'int m_exitCode=1;\n        SPELLinterpreterConfig   m_config;')
    elif name.endswith('SPELLserviceInterpreter.C'):
        text=text.replace('cifStartup.procId = m_service;', 'cifStartup.procId = m_service;\n    cifStartup.service = true;')
        text=text.replace('#include "SPELL_EXC/SPELLserviceInterpreter.H"', '#include "SPELL_EXC/SPELLserviceInterpreter.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        shutdown=body('interpreter_shutdown.cpp').replace('SPELLinterpreter::','SPELLserviceInterpreter::').replace('m_executor','m_serviceImpl')
        shutdown=shutdown.replace('        PyEval_SetTrace(nullptr,nullptr);','        PyEval_SetTrace(nullptr,nullptr);\n        SPELLprocedureManager::instance().cleanupServices();')
        text=section(text,'SPELLserviceInterpreter::~SPELLserviceInterpreter()', 'SPELLserviceInterpreter& SPELLserviceInterpreter::instance()', '''SPELLserviceInterpreter::~SPELLserviceInterpreter()
{
    shutdown();
    s_instance=nullptr;
}
'''+shutdown)
        text=text.replace('m_controller->begin();','m_controller->begin();\n        m_controllerStarted=true;')
        text=text.replace('        m_cif->cleanup(false);', '        { SPELLsafeThreadOperations release("Join service CIF workers"); m_cif->cleanup(false); }')
        text=text.replace('        m_controller->stop();', '''        m_controller->stop();
        { SPELLsafeThreadOperations release("Join service controller");
          static_cast<SPELLcontroller*>(m_controller)->join(); }
        m_controllerStarted=false;''')
        text=text.replace('        // After the execution cycle, wait for the user/server to autorize closure',
            '        m_exitCode = m_serviceImpl->getStatus() == STATUS_FINISHED ? 0 : 1;\n\n        // After the execution cycle, wait for the user/server to autorize closure')
        text=text.replace('        LOG_ERROR(msg);\n        // Notify error','        LOG_ERROR(msg);\n        std::cerr << msg << std::endl;\n        // Notify error')
        text=text.replace('        \t::exit(EIO);', '            throw;')
    elif name == 'src/service/src/SPELLserviceMain.C':
        text=text.replace('    // Initialize the interpeter', '    int exitCode=1;\n    try {\n    // Initialize the interpeter')
        text=text.replace('    interp.mainLoop();', '''    interp.mainLoop(); exitCode=interp.exitCode(); }
    catch (SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
    catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    interp.shutdown();
    delete &interp;
    delete cif;''')
        start=text.index('int main(')
        text=text[:start]+text[start:].replace('    return 0;','    return exitCode;')
    elif name == 'lib/SPELL_CTX/src/SPELLserviceManager.C':
        text=section(text,'void SPELLserviceManager::cleanup()', 'void SPELLserviceManager::startService(', '''void SPELLserviceManager::cleanup()
{
    ServiceMap pending,retired;
    { SPELLmonitor lock(m_lock);
      pending.swap(m_pendingLogin); retired.swap(m_retiredLogin); }
    for (auto& entry : pending) delete entry.second;
    for (auto& entry : retired) delete entry.second;
    delete m_persisTable; m_persisTable=nullptr;
}
//=============================================================================
''')
        # A pending model has one owner until successful login transfers it.
        text=text.replace('\t\t\tm_services.insert( std::make_pair( exec->getModel().getInstanceId(), exec ));\n','')
        start=text.index('void SPELLserviceManager::callback_serviceNotReconnected(')
        end=text.index('//void SPELLserviceManager::recoverExecutor(',start)
        part=text[start:end].replace('\t\tdelete it->second;', '        m_retiredLogin.emplace(instanceId,it->second);')
        text=text[:start]+part+text[end:]
        text=text.replace('if (m_services.count(id) > 0)', 'if (m_services.count(id) > 0 && m_services[id] != exec)')
        text += "\nbool SPELLserviceManager::isActiveOrPending(const std::string& id)\n{\n    SPELLmonitor lock(m_lock);\n    if (m_pendingLogin.count(id)) { LOG_INFO(\"Service watchdog retained pending reconnect: \" + id); return true; }\n    auto found=m_services.find(id);\n    return found!=m_services.end() && found->second->isActive();\n}\n"
        text=text.replace('\tconfig.setContextName(m_contextName);', '    const auto active=m_services.find(config.getInstanceId());\n    if (m_pendingLogin.count(config.getInstanceId()) || (active!=m_services.end() && active->second->isActive())) return;\n\tconfig.setContextName(m_contextName);',1)


    elif name.endswith('SPELLinterpreter.H'):
        text = text.replace('void mainLoop();','void mainLoop();\n        void shutdown();\n        int exitCode() const { return m_exitCode; }')
        text = text.replace('SPELLcontrollerIF*       m_controller;', 'bool m_controllerStarted=false;\n        SPELLcontrollerIF*       m_controller;')
        text = text.replace('SPELLinterpreterConfig   m_config;','int m_exitCode=1;\n        SPELLinterpreterConfig   m_config;')
    elif name.endswith('SPELLinterpreter.C'):
        text = text.replace('#include "SPELL_EXC/SPELLinterpreter.H"','#include "SPELL_EXC/SPELLinterpreter.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = section(text,'SPELLinterpreter::~SPELLinterpreter()', 'SPELLinterpreter& SPELLinterpreter::instance()', '''SPELLinterpreter::~SPELLinterpreter()
{
    shutdown();
    s_instance=nullptr;
}
'''+body('interpreter_shutdown.cpp'))
        text = text.replace('m_controller->begin();','m_controller->begin();\n        m_controllerStarted=true;')
        text = text.replace('        m_cif->cleanup(false);', '        { SPELLsafeThreadOperations release("Join CIF workers"); m_cif->cleanup(false); }')
        text = text.replace('        m_controller->stop();', '''        m_controller->stop();
        { SPELLsafeThreadOperations release("Join command controller");
          static_cast<SPELLcontroller*>(m_controller)->join(); }
        m_controllerStarted=false;''')
        text = text.replace('SPELLprocedureManager::instance().setup(m_config.ctxName);',
            'SPELLprocedureManager::instance().setup(m_config.ctxName);\n        if (m_config.script) SPELLprocedureManager::instance().registerScript(m_procedure);')
        text = text.replace('cifStartup.procName = SPELLprocedureManager::instance().getProcName(m_procedure);',
            'cifStartup.procName = m_config.script ? m_procedure : SPELLprocedureManager::instance().getProcName(m_procedure);')
        text = text.replace('    // After the execution cycle, wait for the user/server to autorize closure',
            '    m_exitCode = m_executor->getStatus() == STATUS_FINISHED ? 0 : 1;\n\n    // After the execution cycle, wait for the user/server to autorize closure')
        text = text.replace('        LOG_ERROR(msg);\n        // Notify error', '        LOG_ERROR(msg);\n        std::cerr << msg << std::endl;\n        // Notify error')
        text = text.replace('startup.persistentFile += m_config.timeId + "_Executor_" + theId;',
            'startup.persistentFile += m_config.timeId + "_Executor_" + theId;\n            if (m_config.recover) startup.persistentFile += "_resume_" + std::to_string(getpid());')
    elif name == 'src/executor/src/SPELLexecutorMain.C':
        text=text.replace('"wp:f:n:c:r:s:"','"wp:f:n:c:r:s:t:"')
        text=text.replace('config.warmstart   = (warm == 1);','config.warmstart   = (warm == 1 || recover == 1);')
        text=text.replace('    // Initialize the interpreter','    int exitCode=1;\n    try {\n    // Initialize the interpreter')
        text=text.replace('    interp.mainLoop();\n\n    return 0;', '''    interp.mainLoop(); exitCode=interp.exitCode(); }
    catch (SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
    catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    interp.shutdown();
    delete &interp;
    delete cif;
    return exitCode;''')
    elif name == 'src/executorcmd/src/SPELLexecutorMain.C':
        text = text.replace('config.warmstart   = (warm == 1);', 'config.warmstart   = (warm == 1 || recover == 1);')
        text = text.replace('    SPELLcif* cif = NULL;', '    SPELLcif* cif = NULL;\n    int exitCode=1;\n    try {')
        text = text.replace('    interp.mainLoop();\n\n    return 0;', '''    interp.mainLoop(); exitCode=interp.exitCode(); }
    catch (SPELLcoreException& error) {
        std::cerr << error.what() << std::endl;
    }
    catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
    }
    interp.shutdown();
    delete &interp;
    delete cif;
    return exitCode;''')
    elif name.endswith('SPELLregistry.C'):
        text = text.replace('#include "SPELL_WRP/SPELLregistry.H"','#include "SPELL_WRP/SPELLregistry.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = re.sub(r'PyObject\* SPELLregistry::getRegistryObject\(\)\s*\{.*?\n\}', '''PyObject* SPELLregistry::getRegistryObject()
{
    // The module owns the registry in the current interpreter. Never cache a
    // Python object in a process-wide singleton across Py_FinalizeEx().
    return SPELLpythonHelper::instance().getObject("spell.lib.registry","REGISTRY");
}''',text,flags=re.S)
        text = text.replace('    PyObject_SetItem( registry, SSTRPY(key), obj );','''    SPELLpython313::Owned pyKey(SSTRPY(key));
    if (!pyKey.get() || PyObject_SetItem(registry,pyKey.get(),obj)<0)
        SPELLpythonHelper::instance().checkError();''')
    elif name.endswith('SPELLexecutorPython.C'):
        text = binding(text,'Executor','EXEC',{
            'startWait':(0,2),'startPrompt':(0,2),'openSubProcedure':(2,2),
            'abort':(0,1),'finish':(0,1),'setUserAction':(3,3),'setStep':(2,2),
            'setByStep':(1,1),'setExecutionDelay':(1,1),'notify':(3,3)})
        text = text.replace('    Py_INCREF(statusStr);\n','').replace('    Py_INCREF(err);\n','')
        text = text.replace('    PyObject* funcObj = PyTuple_GetItem(args,0);', '''    PyObject* funcObj = PyTuple_GetItem(args,0);
    if (!PyFunction_Check(funcObj) || !PyDict_Check(PyTuple_GetItem(args,2))) {
        PyErr_SetString(PyExc_TypeError,"User action requires a Python function, label and configuration dictionary");
        return nullptr;
    }''')
        text = text.replace('    std::string procId    = PYSTR(PyTuple_GetItem(args, 0));', '''    PyObject* config = kwds ? PyDict_GetItemString(kwds,"config") : nullptr;
    if (!config || !PyDict_Check(config) || !PyDict_Check(PyTuple_GetItem(args,1)) ||
        !PyDict_GetItemString(config,Automatic.c_str()) || !PyDict_GetItemString(config,Blocking.c_str()) ||
        !PyDict_GetItemString(config,Visible.c_str())) {
        PyErr_SetString(PyExc_TypeError,"Child procedure requires argument and complete configuration dictionaries");
        return nullptr;
    }
    std::string procId    = PYSTR(PyTuple_GetItem(args, 0));''')
        text = text.replace('SPELLexecutor::instance().setByStep(PyObject_IsTrue(byStep));', '''int enabled=PyObject_IsTrue(byStep);
    if (enabled<0) return nullptr;
    SPELLexecutor::instance().setByStep(enabled);''')
    elif name.endswith('SPELLcifPython.C'):
        text = binding(text,'ClientIF','CIF',{
            'setVerbosity':(0,1),'forcePromptConfirm':(0,1),'write':(1,2),
            'notify':(4,6),'prompt':(3,3),'clearSharedData':(1,2),
            'setSharedData':(4,4),'getSharedData':(2,2),'getSharedDataKeys':(1,1),
            'addSharedDataScope':(1,1),'removeSharedDataScope':(1,1)})
        text = text.replace('abort("Unable to receive prompt answer", true);',
            'abort("Unable to receive prompt answer: " + ex.what(), true);')
        text = text.replace('    PyObject* scopeObj = argumentsA[3];', '''    PyObject* scopeObj = argumentsA[3];
    if (PyList_Check(nameObj) && (!PyList_Check(valueObj) || !PyList_Check(expectedObj) ||
        PyList_Size(nameObj)!=PyList_Size(valueObj) || PyList_Size(nameObj)!=PyList_Size(expectedObj))) {
        PyErr_SetString(PyExc_TypeError,"Shared variable names, values and expectations require equally sized lists");
        return nullptr;
    }''')
        text = text.replace('    PyObject* o_name = PyTuple_GetItem( args, 1 );', '''    else {
        PyErr_SetString(PyExc_ValueError,"Unknown SPELL notification type"); return nullptr;
    }
    PyObject* o_name = PyTuple_GetItem( args, 1 );''')
    elif name.endswith(('SPELLstepPython.C','SPELLgotoPython.C')):
        prefix='Step' if name.endswith('SPELLstepPython.C') else 'Goto'
        text = binding(text,prefix)
        marker=f'static PyObject* {prefix}_Call( PyObject* self, PyObject* args, PyObject* kargs )\n{{'
        assert marker in text
        text=text.replace(marker,marker+'''
    if (kargs && PyDict_Size(kargs)) {
        PyErr_SetString(PyExc_TypeError,"Step and Goto use positional arguments"); return nullptr;
    }''')
    elif name.endswith('SPELLwarmstart.H'):
        text = text.replace('virtual void saveState() = 0;', '''virtual void saveState() = 0;
        virtual std::vector<PyFrameObject*> getFrames() const = 0;
        virtual bool rebindPending(PyFrameObject* frame) = 0;
        virtual PyObject* resume() = 0;''')
    elif name.endswith(('SPELLwsDynamicData.C','SPELLwsStaticData.C','SPELLwsFrame.C','SPELLwsDynamicData.H')):
        replacement = {'SPELLwsDynamicData.C':'ws_dynamic.cpp','SPELLwsStaticData.C':'ws_static.cpp',
                       'SPELLwsFrame.C':'ws_frame.cpp','SPELLwsDynamicData.H':'ws_dynamic.h'}[Path(name).name]
        text = text[:text.index('// FILES TO INCLUDE')] + body(replacement)
    elif name.endswith('SPELLwsStaticData.H'):
        text = text.replace('void cleanup();','void cleanup();\n        void rebind(PyFrameObject* frame) { m_frame = frame; }')
    elif name.endswith('SPELLwsFrame.H'):
        text = text.replace('void reset();','''void reset();
        void refresh();
        void setState(PyObject* state);
        PyObject* getState() const;
        void rebind(PyFrameObject* frame);
        bool isPending() const { return m_pending; }''')
        text = text.replace('void refresh();', 'void refresh();\n        int getReturnOffset() const { return m_returnOffset; }\n        void setReturnOffset(int value) { m_returnOffset=value; }')
        text = text.replace('unsigned int m_lastLine;', 'unsigned int m_lastLine;\n        bool m_pending;\n        int m_returnOffset=0;')
    elif name.endswith('SPELLframeManager.H'):
        text = text.replace('#include "SPELL_EXC/SPELLexecutionModel.H"', '#include "SPELL_EXC/SPELLexecutionModel.H"\n#include "SPELL_EXC/SPELLexecutorConfiguration.H"')
        text = text.replace('void initialize( const std::string& scriptFile );', '''void initialize( const std::string& scriptFile );
        void initialize(const std::string& scriptFile, const SPELLexecutorConfig& configuration, PyObject* environment = nullptr);''')
        text = text.replace('bool                  m_terminated;', 'bool                  m_terminated;\n        bool m_resumePending; // saved continuations require the modern WS adapter')
        text = text.replace('PyObject*             m_definitions;', 'PyObject*             m_definitions;\n        PyObject* m_environment = nullptr;')
        text = text.replace('void checkRuntimeError();','void checkRuntimeError();\n        void rebuildRecoveredModels(PyFrameObject* top);')
        text = text.replace('return (m_initialFrame == m_currentFrame);','return m_modelKeys.size() <= 1;')
    elif name.endswith('SPELLexecutor.H'):
        text = text.replace('static inline SPELLexecutorIF& instance()', 'static bool isAvailable() { return s_instance != nullptr; }\n\n        static inline SPELLexecutorIF& instance()')
    elif name.endswith('SPELLdtaContainer.H'):
        text = text.replace('void incref();', 'void clear(bool releaseValues = true); // detach borrowed links, optionally clear values')
        text = text.replace('std::vector<std::string> m_varOrder;', '// Python 3 dictionaries preserve insertion order and key identity.')
        text = text.replace('PyObject* getDict() { return m_dict; };','''PyObject* getDict() { return m_dict; };
        void setOwner(PyObject* owner) { m_owner=owner; }
        PyObject* getOwner() const { return m_owner; }
        void restoreSnapshot(const std::string& name, PyObject* values, bool notifications);''')
        text = text.replace('PyObject* m_dict;','PyObject* m_dict;\n        PyObject* m_owner=nullptr; // borrowed Python wrapper')
    elif name.endswith('SPELLdtaVariable.H'):
        text = text.replace('void setContainer( SPELLdtaContainer* container );', '''void setContainer( SPELLdtaContainer* container );
        void detachContainer(SPELLdtaContainer* expected) { if (m_container == expected) m_container = nullptr; }''')
        text = text.replace('void setContainer( SPELLdtaContainer* container );','void setContainer( SPELLdtaContainer* container );\n        SPELLdtaContainer* getContainer() const { return m_container; }')
    elif name.endswith(('SPELLdtaContainer.C', 'SPELLdtaContainerObjectMethods.C', 'SPELLdtaVariableObjectMethods.C')):
        replacement = {'SPELLdtaContainer.C':'dta_container.cpp',
            'SPELLdtaContainerObjectMethods.C':'dta_container_bindings.cpp',
            'SPELLdtaVariableObjectMethods.C':'dta_variable_bindings.cpp'}[Path(name).name]
        text = text[:text.index('// FILES TO INCLUDE')] + body(replacement)
    elif name.endswith('SPELLdtaModule.C'):
        text = text.replace('#include "object.h"','#include "object.h"\n'+body('dta_checkpoint.cpp'))
        for kind,prefix in (('Container','container'),('Variable','variable')):
            marker='static PyMethodDef SPELLdta'+kind+'Object_Methods[] =\n{'
            assert marker in text
            text=text.replace(marker,marker+'\n    {"__reduce_ex__",'+prefix+'Reduce,METH_O,"Native checkpoint state"},\n    {"__setstate__",'+prefix+'SetState,METH_O,"Restore native checkpoint state"},')
        # Retain the original public method tables; allocate types per interpreter.
        marker = '//============================================================================\n// Python type specification'
        assert marker in text
        text = text[:text.index(marker)] + body('dta_module.cpp')
    elif name.endswith('SPELLdtaVariable.C'):
        text = text.replace('#include "SPELL_DTA/SPELLdtaVariable.H"', '#include "SPELL_DTA/SPELLdtaVariable.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = section(text, '\t\t\tint longValue = 0;', '\n\t\t}\n\n\t\tm_value = value;', '''            double numeric = PyLong_AsDouble(pyValue);
            if (PyErr_Occurred()) SPELLpythonHelper::instance().checkError();
            SPELLpython313::Owned converted(PyFloat_FromDouble(numeric));
            if (!converted.get()) SPELLpythonHelper::instance().checkError();
            value = converted.get();''')
        guard = '''
    if (!SPELLexecutor::isAvailable())
        THROW_EXCEPTION("SPELL executor unavailable", "Data notifications and prompts require an active executor", SPELL_ERROR_EXECUTION);
'''
        text = text.replace('\tm_name = "";', '\tif (kwds && SPELLdtaContainer::areGlobalnotificationsEnabled()) { ' + guard + ' }\n\tm_name = "";', 1)
        text = text.replace('bool SPELLdtaVariable::shouldNotify()\n{', 'bool SPELLdtaVariable::shouldNotify()\n{\n    if (!SPELLdtaContainer::areGlobalnotificationsEnabled()) return false;' + guard)
        text = text.replace('bool SPELLdtaVariable::promptForValue( std::string& message )\n{', 'bool SPELLdtaVariable::promptForValue( std::string& message )\n{' + guard)
        text = text.replace('PyObject* SPELLdtaVariable::confirmValue()\n{', 'PyObject* SPELLdtaVariable::confirmValue()\n{' + guard)
    elif name.endswith('SPELLpyValue.C'):
        text = text.replace('#include "SPELL_WRP/SPELLpyValue.H"', '#include "SPELL_WRP/SPELLpyValue.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <algorithm>')
        text = text.replace('m_stringValue = PYSTR(pyValue);', 'm_stringValue = SPELLpython313::text(pyValue);')
        text = text.replace('PYSSTR(key), SPELLpyValue(value)', 'SPELLpython313::text(key), SPELLpyValue(value)')
        text = text.replace('return SSTRPY(m_stringValue);', 'return PyUnicode_FromStringAndSize(m_stringValue.data(), m_stringValue.size());')
        text = text.replace('void SPELLpyValue::set( PyObject* pyValue )\n{', '''void SPELLpyValue::set( PyObject* pyValue )
{
    static thread_local std::vector<PyObject*> active;
    struct Recursion {
        std::vector<PyObject*>& stack;
        Recursion(std::vector<PyObject*>& values, PyObject* object): stack(values) {
            if (stack.size() >= 128 || std::find(stack.begin(), stack.end(), object) != stack.end()) {
                PyErr_SetString(PyExc_ValueError, "SPELL values cannot be cyclic or nested beyond 128 levels");
                SPELLpythonHelper::instance().checkError();
            }
            if (Py_EnterRecursiveCall(" while converting a SPELL value")) SPELLpythonHelper::instance().checkError();
            stack.push_back(object);
        }
        ~Recursion() { stack.pop_back(); Py_LeaveRecursiveCall(); }
    } recursion(active, pyValue);
    m_listValue.clear();
    m_dictValue.clear();''')
        text = text.replace('\t\t\tPy_INCREF(item);\n', '')
        text = text.replace('\t\t\tPyDict_SetItemString(dict,key.c_str(),item);', '''            SPELLpython313::Owned pyKey(PyUnicode_FromStringAndSize(key.data(), key.size()));
            if (!item || !pyKey.get() || PyDict_SetItem(dict,pyKey.get(),item)<0) {
                Py_XDECREF(item); Py_DECREF(dict); return nullptr;
            }
            Py_DECREF(item);''')
        text = text.replace('\t\t\tPyList_SetItem(list,idx,item);', '''            if (!item) { Py_DECREF(list); return nullptr; }
            PyList_SET_ITEM(list,idx,item);''')
        text = text.replace('PyObject* list = PyList_New(m_listValue.size());', 'PyObject* list = PyList_New(m_listValue.size());\n        if (!list) return nullptr;')
        text = text.replace('PyObject* dict = PyDict_New();', 'PyObject* dict = PyDict_New();\n        if (!dict) return nullptr;')
        start = 'SPELLpyValue& SPELLpyValue::operator=( const SPELLpyValue& other )'
        assert text.count(start) == 1
        text = text[:text.index(start)] + body('py_value_assignment.cpp')
    elif name.endswith('SPELLframeManager.C'):
        text = text.replace('#include "SPELL_EXC/SPELLframeManager.H"', '#include "SPELL_EXC/SPELLframeManager.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <memory>\n#include <sys/time.h>')
        text = section(text, 'SPELLframeManager::~SPELLframeManager()', 'void SPELLframeManager::initialize(', '''SPELLframeManager::~SPELLframeManager()
{
    // Destruction must not compile a new procedure. The interpreter owns WS;
    // models and the initial-frame slot each own their own frame references.
    for (const auto& item: m_modelMap) delete item.second;
    m_modelMap.clear();
    m_modelKeys.clear();
    m_traceMap.clear();
    m_model = nullptr;
    m_currentFrame = nullptr; // borrowed from an initial frame or model
    Py_XDECREF(m_definitions);
    Py_XDECREF(m_code);
    Py_XDECREF(m_initialFrame);
    Py_XDECREF(m_environment);
}
\n//=============================================================================\n''')
        text = text.replace('        Py_XDECREF(m_currentFrame);\n', '')
        text,count = re.subn(r'void SPELLframeManager::terminate\(\)\s*\{.*?\n\}', '''void SPELLframeManager::terminate()
{
    SPELLpython313::GIL gil;
    m_terminated=true;
    // The active evaluator unwinds with the original control exception. Never
    // rewrite legacy byte offsets or swallow the pending trace exception.
    if (SPELLerror::instance().isExecutionAborted())
        PyErr_SetString(PyExc_RuntimeError,"EXECUTION ABORTED");
    else if (SPELLerror::instance().isExecutionTerminated())
        PyErr_SetString(PyExc_RuntimeError,"EXECUTION TERMINATED");
    else
        PyErr_SetString(PyExc_RuntimeError,"SPELL execution stopped");
}''',text,flags=re.S)
        assert count==1
        text = text.replace('\t\tPy_INCREF(m_currentFrame);\n', '')
        text = text.replace('    m_terminated = false;', '    m_terminated = false;\n    m_resumePending = false;')
        text = text.replace('    m_model = NULL;\n\n    DEBUG("[EF] Clearing breakpoints");', '    m_model = NULL;\n    m_currentFrame = nullptr;\n\n    DEBUG("[EF] Clearing breakpoints");')
        text = section(text, 'void SPELLframeManager::initialize(', 'void SPELLframeManager::saveState()', '''void SPELLframeManager::initialize(const std::string& scriptFile)
{
    initialize(scriptFile, SPELLexecutor::instance().getConfiguration());
}
void SPELLframeManager::initialize(const std::string& scriptFile, const SPELLexecutorConfig& configuration, PyObject* environment)
{
    if (environment && !PyDict_Check(environment))
        THROW_EXCEPTION("Cannot initialize procedure", "Expected namespace dictionary", SPELL_ERROR_EXECUTION);
    Py_XSETREF(m_environment,Py_XNewRef(environment));
    m_filename = scriptFile;
    SPELLvariableMonitor::s_enabled = configuration.isWatchEnabled();
    SPELLresourceMonitor::s_enabled = configuration.isResourcesDisplayEnabled();
    reset();
}
\n//=============================================================================\n''')
        text = section(text, 'void SPELLframeManager::restoreState()', 'void SPELLframeManager::compile()', body('frame_manager_recovery.cpp'))
        text = text.replace('createFrame( m_filename, m_code )', 'createFrame( m_filename, m_code, m_environment )')
        text = text.replace('createFrameModel( callLine, frame );', '''if (m_resumePending && m_warmStart && m_warmStart->rebindPending(frame)) {
        std::string id=m_model->getIdentifier();
        auto replacement=std::make_unique<SPELLexecutionModel>(id,file,frame,m_discardedNames);
        replacement->getVariableMonitor().initialize();
        delete m_model;
        m_model=replacement.release();
        m_modelMap[id]=m_model;
        m_currentFrame=frame;
    } else createFrameModel(callLine,frame);''')
        text = section(text, 'const SPELLexecutionResult SPELLframeManager::execute()', 'void SPELLframeManager::checkRuntimeError()', body('frame_manager_execute.cpp'))
        text = text.replace('SPELLwsWarmStartImpl::setGlobalsFilter( PyDict_Keys(mainDict) );', '''SPELLpython313::Owned filterKeys(PyDict_Keys(mainDict));
    if (!filterKeys.get()) SPELLpythonHelper::instance().checkError();
    SPELLwsWarmStartImpl::setGlobalsFilter(filterKeys.get());''')
        text = section(text, 'void SPELLframeManager::runScript(', 'void SPELLframeManager::callbackEventCall(', body('frame_manager_script.cpp'))
        text = section(text, 'void SPELLframeManager::copyDatabase(', 'void SPELLframeManager::updateDatabases(', body('frame_manager_database.cpp'))
        text = section(text, 'void SPELLframeManager::updateDefinitions(', 'void SPELLframeManager::createFrameModel(', body('frame_manager_definitions.cpp'))
        # Hold every back-frame reference throughout model reconstruction.
        text = text.replace('PyFrameObject* currentFrame = m_initialFrame;', '''std::vector<std::unique_ptr<SPELLpython313::Owned>> frameOwners;
        PyFrameObject* currentFrame = reinterpret_cast<PyFrameObject*>(Py_XNewRef(m_initialFrame));''')
        text = text.replace('frames.push_back(currentFrame);', '''frameOwners.push_back(std::make_unique<SPELLpython313::Owned>(reinterpret_cast<PyObject*>(currentFrame)));
            frames.push_back(currentFrame);''')
        text = text.replace('currentFrame = currentFrame->f_back;', 'currentFrame = PyFrame_GetBack(currentFrame);')
        text = text.replace('PyFrameObject* frame = m_initialFrame;', '''SPELLpython313::Owned frameOwner(Py_XNewRef(m_initialFrame));
    PyFrameObject* frame = m_initialFrame;''')
        text = text.replace('frame = frame->f_back;', '''frameOwner.reset(reinterpret_cast<PyObject*>(PyFrame_GetBack(frame)));
        frame = reinterpret_cast<PyFrameObject*>(frameOwner.get());''')
        text = text.replace('PyEval_EvalFrame( frame );', 'SPELLpython313::Owned result(PyEval_EvalFrame(frame));')
        text = re.sub(r'^.*DEBUG\("Frame (?:stack top|value stack).*\n', '', text, flags=re.M)
        text = text.replace('PYCREPR(frame->f_back)', 'SPELLpython313::text(SPELLpython313::Owned(reinterpret_cast<PyObject*>(PyFrame_GetBack(frame))).get())')
        text = re.sub(r'PY(?:STR|REPR)\((\w+)->f_code->co_filename\)', r'SPELLpython313::filename(\1)', text)
        text = re.sub(r'PYSTR\((\w+)->f_code->co_name\)', r'SPELLpython313::codename(\1)', text)
        text = re.sub(r'\b(\w+)->f_code\b', r'SPELLpython313::FrameCode(\1).get()', text)
        text = re.sub(r'\b(\w+)->f_lineno\b', r'PyFrame_GetLineNumber(\1)', text)
        text = re.sub(r'\b(\w+)->f_lasti\b', r'PyFrame_GetLasti(\1)', text)
        text = re.sub(r'\b(\w+)->f_globals\b', r'SPELLpython313::FrameGlobals(\1).get()', text)
        text = re.sub(r'^\s*PyFrame_(?:FastToLocals|LocalsToFast)\([^;]+;\n', '\n', text, flags=re.M)
        text = section(text, 'void SPELLframeManager::filterDictUpdated()', 'const bool SPELLframeManager::setNewLine(', '''void SPELLframeManager::filterDictUpdated()
{
    PyObject* definitions = PyDict_Keys(SPELLpythonHelper::instance().getMainDict());
    if (!definitions) SPELLpythonHelper::instance().checkError();
    Py_XDECREF(m_definitions);
    m_definitions = definitions;
}
\n//=============================================================================\n''')
    elif name.endswith('SPELLwsWarmStartImpl.H'):
        text = text.replace('#include "SPELL_WS/SPELLwsFrame.H"', 'class SPELLwsFrame; // Private implementation dependency, not required by callers.')
        text = text.replace('\t\tstatic PyObject* s_filterKeys;', '// Filter ownership is per interpreter; see ws_filter.cpp.')
        text = text.replace('void saveState();','''void saveState();
        std::vector<PyFrameObject*> getFrames() const;
        bool rebindPending(PyFrameObject* frame);
        PyObject* resume();''')
        text = text.replace('void removeTopFrame();','''void removeTopFrame();
        PyObject* captureChain();
        void installChain(PyObject* state);
        static PyObject* skipCaller(PyObject* capsule, PyObject* args);''')
        text = text.replace('SPELLwsStorage* m_storage;', 'PyObject* m_lastState;\n        bool m_resuming;\n        bool m_stagePending;')
    elif name.endswith('SPELLwsWarmStartImpl.C'):
        text = text[:text.index('// FILES TO INCLUDE')] + body('ws_controller.cpp')
    elif name.endswith(('SPELLexecutionModel.C', 'SPELLexecutorImpl.C', 'SPELLserviceImpl.C')):
        text = text.replace('// GLOBALS ', '#include "SPELL_UTIL/SPELLpython313.H"\n\n// GLOBALS ', 1)
        text = text.replace('PYSTR(frame->f_code->co_filename)', 'SPELLpython313::filename(frame)')
        text = text.replace('PYSTR(frame->f_code->co_name)', 'SPELLpython313::codename(frame)')
        text = text.replace('frame->f_lineno', 'PyFrame_GetLineNumber(frame)')
        text = text.replace('frame->f_code', 'SPELLpython313::FrameCode(frame).get()')
        if name.endswith('SPELLexecutionModel.C'):
            text = text.replace('\tm_modelId = modelId;', '\tPy_INCREF(m_frame);\n\tm_modelId = modelId;')
            text = text.replace('SPELLexecutionModel::~SPELLexecutionModel()\n{\n}', 'SPELLexecutionModel::~SPELLexecutionModel()\n{\n    Py_XDECREF(m_frame);\n}')
        elif name.endswith(('SPELLexecutorImpl.C','SPELLserviceImpl.C')):
            text = text.replace('    return SPELLexecutor::instance().dispatch(obj, frame, what, args);','''    try {
        int result=SPELLexecutor::instance().dispatch(obj,frame,what,args);
        if (result<0) {
            // Stop dispatch while CPython unwinds its exception tables. A
            // second trace failure would interrupt finally/context managers.
            PyObject* pending=PyErr_GetRaisedException();
            PyEval_SetTrace(nullptr,nullptr);
            PyErr_SetRaisedException(pending);
        }
        return result;
    }
    catch (SPELLcoreException& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what().c_str());
    } catch (const std::exception& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what());
    } catch (...) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,"SPELL dispatch failed");
    }
    PyObject* pending=PyErr_GetRaisedException();
    PyEval_SetTrace(nullptr,nullptr);
    PyErr_SetRaisedException(pending);
    return -1;''')
            cls='SPELLserviceImpl' if name.endswith('SPELLserviceImpl.C') else 'SPELLexecutorImpl'
            text = section(text,'void '+cls+'::installCallingArguments()',
                'void '+cls+'::execute()',body('executor_environment.cpp').replace('SPELLexecutorImpl',cls))
            text = section(text,'\t// Create proc dictionary object and install it',
                '\tbool success = true;' if cls=='SPELLserviceImpl' else '\t// Load SCDB and GDB',body('executor_proc.cpp'))
            if cls=='SPELLserviceImpl':
                text=text.replace('\t\t\tservice.start();', '''            service.start();
            auto& error=SPELLerror::instance();
            result=error.isExecutionAborted() ? EXECUTION_ABORTED :
                error.isExecutionTerminated() ? EXECUTION_TERMINATED : EXECUTION_SUCCESS;''')
                text=text.replace('    DEBUG("[E] Starting service execution");','    DEBUG("[E] Starting service execution");\n    SPELLerror::instance().clearErrors();')
            text = text.replace('PyObject* proc = getVariableManager().getVariableRef(DatabaseConstants::PROC);',
                'PyObject* proc = PyDict_GetItemString(SPELLpythonHelper::instance().getMainDict(),DatabaseConstants::PROC.c_str());')
            text = text.replace('PyObject* prev = PyDict_GetItemString(proc, DatabaseConstants::STEP.c_str());',
                'SPELLpython313::Owned previous(Py_XNewRef(PyDict_GetItemString(proc,DatabaseConstants::STEP.c_str())));\n        PyObject* prev=previous.get();')
            text = text.replace('\t\tPy_INCREF(pyId);\n\t\tPy_INCREF(pyDesc);','')
            text = text.replace('PyDict_SetItemString( proc, DatabaseConstants::STEP.c_str(), list);',
                'PyDict_SetItemString( proc, DatabaseConstants::STEP.c_str(), list);\n        Py_DECREF(list);')
    elif name.endswith('SPELLbytecode.H'):
        text = text.replace('unsigned int end_lineno;', '''unsigned int end_lineno;
            unsigned int body_lineno;
            unsigned int finally_lineno;
            unsigned int finally_end_lineno;
            std::vector<std::pair<unsigned int,unsigned int>> except_ranges;''')
    elif name.endswith('SPELLbytecode.C'):
        text = section(text, '#include "opcode.h"', '// CONSTRUCTOR',
                       '#include "SPELL_UTIL/SPELLanalysis313.H"\n\n//=============================================================================\n')
        text = section(text, 'void SPELLbytecode::analyze()', 'bool SPELLbytecode::isExecutable(',
                       body('analyze_bytecode.cpp') + '\n//=============================================================================\n')
        text = text.replace('(it->try_lineno < lineNo) && (it->end_try_lineno >= lineNo)',
                            '(it->body_lineno <= lineNo) && (it->end_try_lineno >= lineNo)')
        text = section(text, 'bool SPELLbytecode::isInExceptBlock(', 'bool SPELLbytecode::isInFinallyBlock(', '''bool SPELLbytecode::isInExceptBlock(unsigned int lineNo) const {
    for (const auto& block: m_tryBlocks)
        for (const auto& range: block.except_ranges)
            if (range.first <= lineNo && lineNo <= range.second) return true;
    return false;
}
\n//=============================================================================\n''')
        text = text.replace('(it->end_except_lineno < lineNo) && (it->end_lineno >= lineNo)',
                            '(it->finally_lineno > 0) && (it->finally_lineno <= lineNo) && (it->finally_end_lineno >= lineNo)')
        text = text.replace('(it->try_lineno < lineNo) && (it->except_lineno > lineNo)',
                            '(it->body_lineno <= lineNo) && (it->end_try_lineno >= lineNo)')
    elif name.endswith('SPELLvariableMonitor.H'):
        text=text.replace('void analyze();','void analyze(bool force=false);')
        text=text.replace('void initialize();','void initialize(bool force=false);')
    elif name.endswith('SPELLvariableManager.C'):
        # This public method is the explicit on-demand CIF refresh. Automatic
        # status monitoring calls the monitor directly and retains its flag.
        text=text.replace('getVariableMonitor().analyze();','getVariableMonitor().analyze(true);')
    elif name.endswith('SPELLvariableMonitor.C'):
        marker = '// GLOBALS '
        assert text.count(marker) == 1
        text = text[:text.index(marker)] + '#include "SPELL_UTIL/SPELLpython313.H"\n#include <functional>\n' + body('variable_monitor.cpp')
    elif name.endswith('SPELLwsStorage.C'):
        marker = '#define LATEST_MARSHAL_VERSION 2'
        assert text.count(marker) == 1
        text = text[:text.index(marker)] + '''#include "SPELL_UTIL/SPELLpython313.H"
#include <charconv>
#include <cstdint>
#include <zlib.h>
''' + body('ws_storage.cpp')
    elif name.endswith('SPELLgoto.C'):
        text = section(text, '#include "opcode.h"', '// CONSTRUCTOR    : SPELLgoto::SPELLgoto',
                       '#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLpythonHelper.H"\n\n//=============================================================================')
        text = section(text, 'void SPELLgoto::analyze()', 'std::string SPELLgoto::validateGotos()',
                       body('analyze_goto.cpp') + '\n//=============================================================================\n')
        text = text.replace('return (*lit).second;', 'return lit == m_labels.end() ? -1 : static_cast<int>(lit->second);')
    elif name.endswith('SPELLastAnalyzer.H'):
        text = text.replace('void findNodeLines( struct _node* node, unsigned int depth, unsigned int& parDepth, NodeInfo& info );',
                            '// Tokenization replaces the removed private parser node API.')
        text = text.replace('NodeInfo m_currentNode;', 'NodeInfo m_currentNode{};')
    elif name.endswith('SPELLastAnalyzer.C'):
        text = text.replace('#include "node.h"\n#include "token.h"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include <algorithm>')
        text = section(text, 'void SPELLastAnalyzer::process(', 'bool SPELLastAnalyzer::isSimpleLine(',
                       body('analyze_source.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLlnotab.H'):
        text = text.replace('return m_lines.front();', 'return m_lines.empty() ? -1 : m_lines.front();')
    elif name.endswith('SPELLlnotab.C'):
        text = text.replace('#include "SPELL_EXC/SPELLlnotab.H"', '#include "SPELL_EXC/SPELLlnotab.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLpythonHelper.H"')
        text = section(text, 'void SPELLlnotab::analyze(', 'const int SPELLlnotab::lineAfter(',
                       body('analyze_lines.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLpythonMonitors.H'):
        text = section(text, '\tvirtual ~SPELLsafePythonOperations()', '\nprivate:', '''
    virtual ~SPELLsafePythonOperations() noexcept(false)
    {
        // Do not throw a second exception during C++ stack unwinding.
        try {
            if (std::uncaught_exceptions() == 0)
                SPELLpythonHelper::instance().checkError();
        } catch (...) {
            SPELLpythonHelper::instance().releaseGIL(m_state);
            throw;
        }
        SPELLpythonHelper::instance().releaseGIL(m_state);
    };
''')
    elif name.endswith('SPELLpythonHelper.H'):
        text = text.replace('PyFrameObject* createFrame( const std::string& filename, PyCodeObject* code );',
            'PyFrameObject* createFrame( const std::string& filename, PyCodeObject* code, PyObject* globals = nullptr );')
        text = text.replace('#define __SPELL_PYHELPER_H__', '#define __SPELL_PYHELPER_H__\n#include <thread>')
        text = text.replace('bool m_initialized;', '''bool m_initialized;
        bool m_ownsInterpreter = false;
        bool m_frameworkLoaded = false;
        bool m_frameworkRetired = false;
        std::thread::id m_ownerThread;
        PyThreadState* m_embeddedThread = nullptr;''')
    elif name.endswith('SPELLpythonHelper.C'):
        text = text.replace('#include "Python-ast.h"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLanalysis313.H"\n#include <memory>')
        text = text.replace('#    include "code.h"\n', '')
        text = section(text, 'PyCodeObject* SPELLpythonHelper::compile(',
                       'PyFrameObject* SPELLpythonHelper::createFrame(',
                       body('helper_compile.cpp') + '\n//=============================================================================\n')
        text = section(text, 'void SPELLpythonHelper::initialize()',
                       'bool SPELLpythonHelper::isInstance( PyObject* object, const std::string& className',
                       body('helper_lifecycle.cpp') + '\n//=============================================================================\n')
        text = section(text, 'void SPELLpythonHelper::checkError()',
                       '// METHOD    : SPELLpythonHelper::newInstance', '''void SPELLpythonHelper::checkError()
{
    SPELLpython313::GIL gil;
    std::unique_ptr<SPELLcoreException> error(SPELLerror::instance().errorToException());
    if (error) throw *error;
}
\n//=============================================================================\n''')
        text = section(text, 'PyFrameObject* SPELLpythonHelper::createFrame(',
                       'void SPELLpythonHelper::checkError()', body('helper_frames.cpp'))
        text = text.replace('PyEval_CallObjectWithKeywords(', 'PyObject_Call(')
        text = text.replace('    Py_XINCREF(result);\n    DEBUG("[PYH] New instance end', '    DEBUG("[PYH] New instance end')
        text = text.replace('    Py_INCREF(moduleObj);\n    DEBUG("[PYH] Get module done', '    DEBUG("[PYH] Get module done')
        text = text.replace('    PyObject* moduleObj = getModule(module);',
                            '    SPELLpython313::Owned moduleOwner(getModule(module));\n    PyObject* moduleObj = moduleOwner.get();')
        # Replace the old builtin mutation functions, keeping unrelated APIs.
        for function in ('getMainDict','install','importAllFrom','updateBuiltinsWith'):
            text,count = re.subn(r'(?:PyObject\*|void) SPELLpythonHelper::'+function+r'\([^\n]*\)\s*\{.*?\n\}', '', text, flags=re.S)
            assert count == (2 if function == 'install' else 1), (function,count)
        text += '\n'+body('helper_namespace.cpp')
    elif name.endswith('SPELLutils.C'):
        text = text.replace('#include "SPELL_UTIL/SPELLbase.H"', '#include "SPELL_UTIL/SPELLbase.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = section(text, 'void SPELLutils::dumpInterpreterInfo(',
                       '// FUNCTION:    SPELLutils::dumpString()',
                       body('dump_state.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLlogPython.C'):
        text = text.replace('#include "structmember.h"','#include "structmember.h"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <exception>')
        text = text.replace('static PyObject* KEY_SEVERITY = STRPY("severity");\nstatic PyObject* KEY_LEVEL    = STRPY("level");',
                            '// Keyword lookup must not allocate Python objects before Py_Initialize.')
        text = text.replace('PyDict_Contains( kargs, KEY_SEVERITY )', 'PyDict_GetItemString( kargs, "severity" ) != nullptr')
        text = text.replace('PyDict_Contains( kargs, KEY_LEVEL )', 'PyDict_GetItemString( kargs, "level" ) != nullptr')
        text = re.sub(r'static PyTypeObject Log_Type =\s*\{.*?\n\};','// Logger type belongs to the active interpreter.',text,flags=re.S)
        start = text.index('static PyObject* Log_Call(',text.index('static PyObject* Log_Call(')+1)
        text = text[:start]+body('log_binding.cpp')
    elif name.endswith('SPELLerror.C'):
        text = text.replace('#include "SPELL_UTIL/SPELLerror.H"', '#include "SPELL_UTIL/SPELLerror.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        # These setters deliberately leave a Python exception for a C callback
        # to return. A checking monitor consumed it before the caller saw it.
        text = text.replace('SPELLsafePythonOperations ops("terminate");', 'SPELLpython313::GIL ops;')
        text = text.replace('SPELLsafePythonOperations ops("SPELLerror::executionTerminated");', 'SPELLpython313::GIL ops;')
        # These two objects are never read. They leaked interpreter-owned types
        # across finalization; the actual control protocol uses RuntimeError.
        text = text.replace('    PyType_Ready(&ExecutionAborted_Type);\n    m_excExecutionAborted = (PyObject*) PyObject_New( PyExecutionAbortedObject, &ExecutionAborted_Type );\n    PyType_Ready(&ExecutionTerminated_Type);\n    m_excExecutionTerminated = (PyObject*) PyObject_New( PyExecutionTerminatedObject, &ExecutionTerminated_Type );',
                            '    m_excExecutionAborted = nullptr;\n    m_excExecutionTerminated = nullptr;')
        text = section(text, 'SPELLcoreException* SPELLerror::errorToException()',
                       '// METHOD    : SPELLerror::throwSyntaxException',
                       body('error_conversion.cpp') + '\n//=============================================================================\n')
        text = text.replace('PYSTR(tb->tb_frame->f_code->co_filename)', 'SPELLpython313::filename(tb->tb_frame)')
        # The remaining getPythonError fetch owns its three references.
        needle = 'PyErr_Fetch( &ptype, &pvalue, &ptraceback );'
        assert text.count(needle) == 1
        text = text.replace(needle, needle + '''
        SPELLpython313::Owned typeOwner(ptype), valueOwner(pvalue), tracebackOwner(ptraceback);''')
        text = text.replace('DEBUG("[ERR] Error already tracked");\n\t\t\treturn;',
                            'DEBUG("[ERR] Error already tracked");\n\t\t\tdelete exc;\n\t\t\treturn;')
    if name.endswith(('SPELLipcClientInterface.H','SPELLipcServerInterfaceSingle.H','SPELLipcChannel.H')):
        text='#include <atomic>\n'+text
        text=re.sub(r'bool\s+(m_connected|m_removeClient);',r'std::atomic_bool \1;',text)
    if name.endswith('SPELLipcChannel.C'):
        text=text.replace('std::vector<std::string> SPELLipcChannel::getOngoingRequests()\n{',
            'std::vector<std::string> SPELLipcChannel::getOngoingRequests()\n{\n    SPELLmonitor lock(m_dataLock);')
    if name.endswith('SPELLipcTrash.H'):
        text=text.replace('void place(', 'bool place(')
    if name.endswith('SPELLipcTrash.C'):
        text=section(text,'void SPELLipcTrash::place(', 'void SPELLipcTrash::run()', '''bool SPELLipcTrash::place(SPELLipcIncomingBase* message)
{
    SPELLmonitor lock(m_dataLock);
    if (!m_trashWorking) return false; // caller retains an unstarted worker
    m_messages.push_back(message);
    try { message->start(); }
    catch (...) { m_messages.pop_back(); throw; }
    return true; // collector owns and joins every admitted worker
}

''')
    if name.endswith(('SPELLipcClientInterface.C','SPELLipcServerInterface.C','SPELLipcServerInterfaceSingle.C')):
        text='#include <memory>\n'+text
        for kind,variable in [('Request','ireq'),('Message','imsg')]:
            pattern=r'SPELLipcIncoming'+kind+r'\* '+variable+r' = new SPELLipcIncoming'+kind+r'\(([^;]+)\);'
            replacement=r'auto '+variable+r' = std::make_unique<SPELLipcIncoming'+kind+r'>(\1);'
            text,count=re.subn(pattern,replacement,text)
            assert count==1,(name,kind,count)
            text=re.sub(r'^\s*'+variable+r'->start\(\);\n','\n',text,flags=re.M)
            text=text.replace('m_trash.place('+variable+');',
                'if (m_trash.place('+variable+'.get())) '+variable+'.release();')
    if name.endswith('SPELLipcClientInterface.H'):
        text='#include <mutex>\n'+text
        text=re.sub(r'(SPELLmutex\s+m_lock;)', r'\1\n        std::mutex m_lifecycleMutex;',text)
    if name.endswith('SPELLipcClientInterface.C'):
        text=text.replace('void SPELLipcClientInterface::connect( bool reconnect )\n{',
            'void SPELLipcClientInterface::connect( bool reconnect )\n{\n    std::lock_guard<std::mutex> lifecycle(m_lifecycleMutex);')
        text=text.replace('    if (isConnected()) throw SPELLipcError("Client already connected");\n    if (m_channel) { delete m_channel; m_channel=nullptr; }\n    else delete m_socket;\n    m_socket=nullptr;', '''    SPELLipcChannel* previous=nullptr;
    SPELLsocket* previousSocket=nullptr;
    { SPELLmonitor lock(m_lock);
      if (m_connected) throw SPELLipcError("Client already connected");
      previous=m_channel; previousSocket=m_socket;
      m_channel=nullptr; m_socket=nullptr; }
    if (previous) delete previous; else delete previousSocket;''')
        text=text.replace('    m_connected = true;\n\n    if (m_channel != NULL) delete m_channel;\n    m_channel = createChannel();\n    m_channel->connect();', '''    {
        SPELLmonitor lock(m_lock);
        m_channel=createChannel();
        m_connected=true;
        try { m_channel->connect(); }
        catch (...) { m_connected=false; throw; }
    }''')
        text=section(text,'void SPELLipcClientInterface::disconnect()', 'void SPELLipcClientInterface::connectionLost(', '''void SPELLipcClientInterface::disconnect()
{
    std::lock_guard<std::mutex> lifecycle(m_lifecycleMutex);
    SPELLipcChannel* channel=nullptr;
    SPELLsocket* socket=nullptr;
    {
        SPELLmonitor lock(m_lock);
        m_connected=false;
        channel=m_channel; socket=m_socket;
        m_channel=nullptr; m_socket=nullptr;
    }
    cancelOutgoingRequests();
    cancelIncomingRequests();
    m_mailbox.shutdown();
    // Response workers observe the revoked slot under m_lock. Join channel
    // threads outside that lock, so finishing response workers can progress.
    if (channel) { channel->disconnect(); delete channel; }
    else delete socket;
    m_trash.shutdown();
    m_trash.join();
}

''')
        text=text.replace('\t\tmsg.setSequence(m_ipcSequence++);\n\t    m_channel->getWriter().send(msg);',
            '\t\tif (!m_connected || !m_channel) return;\n\t\tmsg.setSequence(m_ipcSequence++);\n\t    m_channel->getWriter().send(msg);')
        text=section(text,'void SPELLipcClientInterface::cancelOutgoingRequests()',
                     'void SPELLipcClientInterface::cancelIncomingRequests()', '''void SPELLipcClientInterface::cancelOutgoingRequests()
{
    std::list<std::string> pending;
    { SPELLmonitor lock(m_lock); pending.swap(m_outgoingRequests); }
    for (const auto& id:pending) m_mailbox.cancel(id);
}

''')
        start=text.index('SPELLipcMessage SPELLipcClientInterface::performRequest(')
        end=text.index('void SPELLipcClientInterface::initialize(',start)
        part=text[start:end]
        part=part.replace('                m_mailbox.prepare( reqId );', '''                {
                    SPELLmonitor lock(m_lock);
                    if (!m_connected || !m_channel) break;
                    m_mailbox.prepare(reqId);''')
        part=part.replace('                DEBUG(NAME + "Waiting response from peer");',
            '                } // request admission and channel send are atomic with disconnect\n                DEBUG(NAME + "Waiting response from peer");')
        part=part.replace('                std::list<std::string>::iterator it = std::find(',
            '                { SPELLmonitor lock(m_lock);\n                std::list<std::string>::iterator it = std::find(')
        part=part.replace('                retries = 2;', '                }\n                retries = 2;')
        part=part.replace('    }\n\n    return response;',
            '        { SPELLmonitor lock(m_lock); m_outgoingRequests.remove(reqId); }\n    }\n\n    return response;')
        text=text[:start]+part+text[end:]
    if name.endswith('SPELLipcServerInterface.C'):
        text=text.replace('int SPELLipcServerInterface::getFreeClientKey()\n{',
            'int SPELLipcServerInterface::getFreeClientKey()\n{\n    SPELLmonitor lock(m_clientLock);')
        text=text.replace('\t\t\t\t\tm_usedClientKeys.push_back(key);',
            '\t\t\t\t\t{ SPELLmonitor lock(m_clientLock); m_usedClientKeys.push_back(key); }')
        text=section(text,'void SPELLipcServerInterface::cancelOutgoingRequests(',
                     'void SPELLipcServerInterface::cancelIncomingRequests(', '''void SPELLipcServerInterface::cancelOutgoingRequests(int peerKey)
{
    std::vector<std::string> pending;
    {
        SPELLmonitor lock(m_clientLock);
        auto found=m_clients.find(peerKey);
        if (found!=m_clients.end() && found->second)
            pending=found->second->getOngoingRequests();
    }
    for (const auto& id:pending) m_mailbox.cancel(id);
}

''')
        text=section(text,'void SPELLipcServerInterface::addClient(', 'void SPELLipcServerInterface::removeClient(', '''void SPELLipcServerInterface::addClient(int key,SPELLsocket* socket)
{
    std::unique_ptr<SPELLsocket> socketOwner(socket);
    auto channel=std::make_unique<SPELLipcChannel>(m_ifcName,socket,key,*this);
    socketOwner.release(); // the channel now owns the accepted socket
    {
        SPELLmonitor lock(m_clientLock);
        m_clients[key]=channel.get();
        try { channel->connect(); }
        catch (...) {
            m_clients[key]=nullptr;
            m_usedClientKeys.erase(std::remove(m_usedClientKeys.begin(),m_usedClientKeys.end(),key),m_usedClientKeys.end());
            throw;
        }
        channel.release();
    }
    LOG_INFO(NAME + "Added client " + ISTR(key));
    m_clientConnectionEvent.set();
}

''')
    if name == 'include/SPELL_PRC/SPELLprocessManager.H':
        text='#include <mutex>\n#include <condition_variable>\n#include <thread>\n'+text
        text=text.replace('class SPELLprocessManager\n{',body('process_subscription.h')+'\nclass SPELLprocessManager\n{')
        text=text.replace('std::list<SPELLprocessListener*>', 'std::list<std::shared_ptr<SPELLprocessSubscription>>')
    if name == 'lib/SPELL_PRC/src/SPELLprocessManager.C':
        start=text.index('void SPELLprocessManager::addListener(')
        text=text[:start]+'''void SPELLprocessManager::addListener(const std::string& identifier,SPELLprocessListener* listener)
{
    if (!listener) return;
    SPELLmonitor lock(m_lock);
    auto& entries=m_listeners[identifier];
    for (const auto& entry:entries) if (entry->listener==listener) return;
    entries.push_back(std::make_shared<SPELLprocessSubscription>(listener));
}

void SPELLprocessManager::removeListener(const std::string& identifier,SPELLprocessListener* listener)
{
    SPELLprocessListeners removed;
    {
        SPELLmonitor lock(m_lock);
        auto found=m_listeners.find(identifier);
        if (found==m_listeners.end()) return;
        auto& entries=found->second;
        for (auto it=entries.begin();it!=entries.end();) {
            if ((*it)->listener==listener) { removed.push_back(*it);it=entries.erase(it); }
            else ++it;
        }
        if (entries.empty()) m_listeners.erase(found);
    }
    // Callbacks may invoke manager methods; drain outside the registry lock.
    for (const auto& entry:removed) entry->cancel();
}
'''
        for event in ('Started','Finished','Killed','Failed'):
            extra=', int retValue' if event=='Finished' else ''
            args=',retValue' if event=='Finished' else ''
            text+='\nvoid SPELLprocessManager::fireProcess'+event+'(std::string identifier'+extra+')\n{\n'
            text+='''    SPELLprocessListeners snapshot;
    { SPELLmonitor lock(m_lock);
      auto found=m_listeners.find(identifier);
      if (found!=m_listeners.end()) snapshot=found->second; }
    for (const auto& entry:snapshot)
'''
            text+='        entry->invoke([&](SPELLprocessListener* listener){ listener->process'+event+'(identifier'+args+'); });\n}\n'
    if name.endswith('SPELLsocket.C'):
        marker='SPELLsocket::SPELLsocket('
        guard='''namespace {
class SPELLsocketOwnedFd {
    int descriptor;
public:
    explicit SPELLsocketOwnedFd(int fd):descriptor(fd) {}
    ~SPELLsocketOwnedFd() { if (descriptor>=0) ::close(descriptor); }
    void release() { descriptor=-1; }
};
}
'''
        text=text.replace(marker,guard+marker,1)
        text=text.replace('    int socketFd = socket(AF_INET, SOCK_STREAM, 0);',
            '    int socketFd = socket(AF_INET, SOCK_STREAM, 0);\n    SPELLsocketOwnedFd ownership(socketFd);')
        text=text.replace('            // Set reuse address',
            '            SPELLsocketOwnedFd ownership(socketFd);\n            // Set reuse address')
        text=text.replace('            in_port_t port = ntohs(client_addr.sin_port);',
            '            SPELLsocketOwnedFd ownership(newfd);\n            in_port_t port = ntohs(client_addr.sin_port);')
        text=text.replace('return new SPELLsocket( newfd, user, groups);',
            'auto* result=new SPELLsocket(newfd,user,groups); ownership.release(); return result;')
        text=text.replace('return new SPELLsocket(socketFd, "spell",{});',
            'auto* result=new SPELLsocket(socketFd,"spell",{}); ownership.release(); return result;')
        text=text.replace('return new SPELLsocket( socketFd , "spell",{});',
            'auto* result=new SPELLsocket(socketFd,"spell",{}); ownership.release(); return result;')
    if name.endswith('SPELLipcClientInterface.H'):
        text=text.replace('std::mutex m_lifecycleMutex;', 'std::mutex m_lifecycleMutex;\n        std::atomic_bool m_closed{false};')
    if name.endswith('SPELLipcClientInterface.C'):
        text='#include <chrono>\n'+text
        text=section(text,'void SPELLipcClientInterface::connect(', 'SPELLipcChannel* SPELLipcClientInterface::createChannel(', body('client_connection.cpp'))
        text=text.replace('void SPELLipcClientInterface::disconnect()\n{', 'void SPELLipcClientInterface::disconnect()\n{\n    m_closed=true;\n    m_readyEvent.set();')
        text=section(text,'int SPELLipcClientInterface::readMyKey()', 'void SPELLipcClientInterface::writeMyKey(', r'''int SPELLipcClientInterface::readMyKey()
{
    unsigned char bytes[2];
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    for (auto& byte:bytes) {
        while (true) {
            if (m_closed) throw SPELLipcError("Key handshake cancelled");
            if (std::chrono::steady_clock::now()>=deadline) throw SPELLipcError("Key handshake timed out");
            if (m_socket->waitData(100)) break;
        }
        if (m_socket->receive(&byte,1)!=1) throw SPELLipcError("Cannot read client key");
    }
    return (bytes[0]<<8)|bytes[1];
}

''')
        text=section(text,'void SPELLipcClientInterface::setReady()', 'void SPELLipcClientInterface::cancelOutgoingRequests()', r'''void SPELLipcClientInterface::setReady()
{
    m_readyEvent.set();
}

void SPELLipcClientInterface::waitReady()
{
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    while (m_readyEvent.isClear()) {
        if (m_closed || !m_connected) throw SPELLipcError("Connection readiness cancelled");
        if (std::chrono::steady_clock::now()>=deadline) throw SPELLipcError("Connection readiness timed out");
        m_readyEvent.wait(100);
    }
    if (m_closed || !m_connected) throw SPELLipcError("Connection readiness cancelled");
}

''')
        text=text.replace('    // Socket is closed at this moment\n    m_connected = false;', '    // Socket is closed at this moment\n    m_connected = false;\n    cancelOutgoingRequests();')
    if name.endswith('SPELLsocket.H'):
        text=text.replace('const int& port );','const int& port, const std::atomic_bool* cancelled = nullptr );')
    if name.endswith('SPELLsocket.C'):
        text='#include <chrono>\n#include <arpa/inet.h>\n'+text
        text=section(text,'SPELLsocket* SPELLsocket::connect(', 'SPELLsocket* SPELLsocket::listen(', body('socket_connect.cpp'))
        text=text.replace('socket(AF_INET, SOCK_STREAM, 0)', 'socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0)')
        text=text.replace('accept(socketFd, (struct sockaddr *)&client_addr, &addrlen)', 'accept4(socketFd, (struct sockaddr *)&client_addr, &addrlen, SOCK_CLOEXEC)')
    if name.endswith('SPELLserverCif.H'):
        text='#include <atomic>\n#include <mutex>\n#include <condition_variable>\n#include <thread>\n'+text
        text=text.replace('std::atomic_bool m_ready;', r'''std::atomic_bool m_ready;
        std::mutex m_reconnectMutex;
        std::condition_variable m_reconnectWake;
        std::thread m_reconnectThread;
        bool m_reconnectPending=false;
        bool m_reconnectStop=false;
        unsigned long m_reconnectGeneration=0;
        void reconnectLoop();
        void stopReconnect();''')
    if name.endswith('SPELLserverCif.C'):
        text='#include <chrono>\n'+text
        text=text.replace('SPELLserverCif::~SPELLserverCif()\n{', 'SPELLserverCif::~SPELLserverCif()\n{\n    stopReconnect();')
        text=text.replace('    m_ifc->initialize( this );', '    m_ifc->initialize( this );\n    m_reconnectThread=std::thread(&SPELLserverCif::reconnectLoop,this);')
        text=text.replace('void SPELLserverCif::specificCleanup( bool force )\n{', 'void SPELLserverCif::specificCleanup( bool force )\n{\n    stopReconnect();')
        text=section(text,'void SPELLserverCif::processConnectionError(', 'void SPELLserverCif::processConnectionClosed(', body('cif_reconnect.cpp'))
    if name == 'lib/SPELL_UTIL/src/SPELLtime.C':
        text='#include <limits>\n#include <stdexcept>\n'+text
        text=section(text,'SPELLtime SPELLtime::operator+(', 'bool SPELLtime::operator<(', body('time_arithmetic.cpp'))
    if name == 'lib/SPELL_CTX/src/SPELLexecutorManager.C':
        # executorLogin owns attachment; the completion callback only publishes
        # the already-attached model in the active registry.
        duplicate='\t\tSPELLprocessManager::instance().attachProcess( exec->getModel().getInstanceId(),  exec->getModel().getPID() );\n'
        assert text.count(duplicate)==1
        text=text.replace(duplicate,'')
    if name == 'lib/SPELL_CTX/src/SPELLexecutor.C':
        # A replacement context has no surviving GUI client pointer. Marking it
        # CONNECTED drops acknowledged notifications in forwardMessageToClient
        # and leaves the original child stuck even after a new GUI sends Run.
        connected='\t\tm_clientConnection = CLI_CONNECTED;\n'
        assert text.count(connected)==1
        text=text.replace(connected,
            '\t\tm_clientConnection = controllingClient ? CLI_CONNECTED : CLI_NO_CLIENT;\n')
        attach='\t\tSPELLprocessManager::instance().attachProcess( m_model.getInstanceId(), m_model.getPID() );'
        assert text.count(attach)==1
        text=text.replace(attach,r'''        if (!processOk()) {
            m_processStartedEvent.clear();
            SPELLprocessManager::instance().attachProcess(m_model.getInstanceId(),m_model.getPID());
            if (m_processStartedEvent.wait(3000) || !processOk())
                THROW_EXCEPTION("Cannot reconnect executor", "Process attachment did not become ready", SPELL_ERROR_PROCESS);
        }''')
    if name.endswith('SPELLserverCif.H'):
        text=text.replace('bool waitAcknowledge( const SPELLipcMessage& msg );',
            'bool waitAcknowledge(const SPELLipcMessage& msg,unsigned long generation);\n        void sendAcknowledged(const SPELLipcMessage& msg);')
    if name.endswith('SPELLserverCif.C'):
        text,count=re.subn(r'do\s*\{\s*sendGUIMessage\(msg\);\s*\}\s*while\s*\(!isClosing\(\) && !waitAcknowledge\(msg\)\);',
            'sendAcknowledged(msg);',text)
        assert count==4,(name,'acknowledged notifications',count)
        text=section(text,'bool SPELLserverCif::waitAcknowledge(', 'void SPELLserverCif::specificNotifyError(', body('cif_acknowledge.cpp'))
    return text.encode('utf-8')


def apply_tree(source):
    changed = {}
    for name, before in PREIMAGES.items():
        path = source / name
        updated = apply(name, path.read_bytes())
        path.write_bytes(updated)
        changed[name] = {'upstream_sha256': before, 'sha256': hashlib.sha256(updated).hexdigest()}
    header = source / 'include/SPELL_UTIL/SPELLpython313.H'
    header.write_bytes((ROOT / header.name).read_bytes())
    changed[header.relative_to(source).as_posix()] = {
        'new': True, 'sha256': hashlib.sha256(header.read_bytes()).hexdigest()}
    header = source/'include/SPELL_UTIL/SPELLbinding313.H'
    header.write_bytes((ROOT/header.name).read_bytes())
    changed[header.relative_to(source).as_posix()] = {'new':True,'sha256':hashlib.sha256(header.read_bytes()).hexdigest()}
    bridge = source/'include/SPELL_UTIL/SPELLanalysis313.H'
    bridge.write_bytes((ROOT/bridge.name).read_bytes())
    embedded = source/'include/SPELL_UTIL/SPELLanalysisSource.H'
    support = body('analysis_support.py')
    assert ')SPELL_ANALYSIS"' not in support
    embedded.write_text('// SPDX-License-Identifier: GPL-3.0-or-later\nstatic const char analysisSource[] = R"SPELL_ANALYSIS(' + support + ')SPELL_ANALYSIS";\n',encoding='utf-8')
    for path in (bridge, embedded):
        changed[path.relative_to(source).as_posix()] = {'new':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    for name in ('SPELLcontinuation313.H','SPELLcontinuationCodec.H'):
        path = source/'include/SPELL_WS'/name
        path.write_bytes((ROOT/name).read_bytes())
        changed[path.relative_to(source).as_posix()] = {'new':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    embedded = source/'include/SPELL_WS/SPELLcontinuationSource.H'
    support = body('continuation_codec.py')
    production = [p for p in sorted(ROOT.iterdir()) if p.is_file() and not p.name.startswith('qualify_')]
    identity = hashlib.sha256(Path(__file__).read_bytes()+b''.join(
        p.name.encode()+b'\0'+p.read_bytes() for p in production)).hexdigest()
    assert ')SPELL_CONT"' not in support
    embedded.write_text('// SPDX-License-Identifier: GPL-3.0-or-later\nstatic const char continuationSourceIdentity[] = "'+identity+'";\nstatic const char continuationSource[] = R"SPELL_CONT('+support+')SPELL_CONT";\n',encoding='utf-8')
    changed[embedded.relative_to(source).as_posix()] = {'new':True,'sha256':hashlib.sha256(embedded.read_bytes()).hexdigest()}
    return changed
