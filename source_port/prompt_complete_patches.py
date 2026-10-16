"""Distinguish an empty supplied default and expose native reminder timing."""
import hashlib

HEADER='include/SPELL_CIF/SPELLpromptDefinition.H'
PREIMAGES={
 HEADER:'98266eda57b7c0d47178e8c972c6d8258dcd3f2863f196d573810b3ca6ad1f93',
 'lib/SPELL_CIF/src/SPELLcifHelper.C':'6c04bd6a5bfcfeee50d6e51f910b56a1d27f238534398e4a2dfbe07a99a31724',
 'lib/SPELL_CIFS/src/SPELLserverCif.C':'66d071d4d6ed272b60fdc43cdd23bd429046921100ee3a7eb198f6eba3daf468',
 'lib/SPELL_CIFS/src/SPELLrequestProcessor.C':'25ee34bf236f671f6b6329c12368e2162032638d09208ddf7fdad6da0b28ad9b',
}


def apply(name,source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Complete prompt preimage differs: '+name)
    text=source.decode('utf-8')
    def replace(before,after,count=1):
        nonlocal text
        if text.count(before)!=count:raise ValueError('Complete prompt anchor differs: '+before)
        text=text.replace(before,after)
    if name==HEADER:
        replace('std::string defaultAnswer;','std::string defaultAnswer;\n\tbool defaultProvided = false;')
    elif name.endswith('SPELLcifHelper.C'):
        replace('def.defaultAnswer = "";','def.defaultAnswer = "";\n\tdef.defaultProvided = false;')
        replace('if (deflt != "")','if (argumentsC.hasModifier(LanguageModifiers::Default))')
        replace('def.defaultAnswer = deflt;',
            'def.defaultAnswer = deflt;\n                def.defaultProvided = argumentsC.hasModifier(LanguageModifiers::Default);',2)
        anchor='\n//=============================================================================\n// METHOD    : SPELLcifHelper::getPythonResult()'
        index=text.index(anchor);before=text[:index];after=text[index:]
        assert before.rstrip().endswith('}')
        end=before.rfind('}')
        before=before[:end]+'    if (!def.defaultAnswer.empty()) def.defaultProvided = true;\n'+before[end:]
        text=before+after
    else:
        receiver='m_promptMessage' if name.endswith('SPELLserverCif.C') else 'response'
        anchor=receiver+'.set(MessageField::FIELD_DEFAULT, def.defaultAnswer);'
        extra=('\n    '+receiver+'.set("DefaultProvided", def.defaultProvided ? "True" : "False");'
            '\n    '+receiver+'.set("TimeoutMicroseconds", ISTR('
            'static_cast<long double>(def.timeout.getSeconds()) * 1000000.L'
            ' + def.timeout.getMilliseconds() * 1000.L + def.timeout.getMicroseconds()));')
        replace(anchor,anchor+extra)
        if name.endswith('SPELLserverCif.C'):
            replace('if (!m_promptDef.defaultAnswer.empty() && seconds > 0)',
                    'if (m_promptDef.defaultProvided && seconds > 0)')
    return text.encode('utf-8')
