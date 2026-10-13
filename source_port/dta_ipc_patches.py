"""Checked original dictionary IPC port: native types, payloads and ownership.

SPDX-License-Identifier: GPL-3.0-or-later
The original client expression-evaluation behavior is retained for Development.
Malformed fields and unknown keys reject before evaluation or mutation.
"""
import hashlib

SOURCE = 'lib/SPELL_CIFS/src/SPELLrequestProcessor.C'
ORIGINAL = 'f0363fc5174c2000c18c76fc5ea1d99a11678dd3baf4ca54ad4349d4ed669b4f'


def apply(name, original, ported):
    if name != SOURCE or any(hashlib.sha256(data).hexdigest() != ORIGINAL for data in (original, ported)):
        raise ValueError('Unexpected original or ported dictionary IPC source')
    text = ported.decode('utf-8')
    text = text.replace('#include "SPELL_WRP/SPELLpyHandle.H"',
        '#include "SPELL_WRP/SPELLpyHandle.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <algorithm>\n#include <charconv>\n#include <stdexcept>')
    before = '''    PyTypeObject* type = reinterpret_cast<PyTypeObject*>(dict->ob_type);
    return std::string(type->tp_name) == "spell.lib.adapter.data.DataContainer";'''
    assert text.count(before) == 1
    text = text.replace(before, '''    if (!dict) return false;
    SPELLpython313::Owned module(PyImport_ImportModule(MOD_NAME(libSPELL_DTA)));
    SPELLpython313::Owned type(module.get() ? PyObject_GetAttrString(module.get(), "DataContainer") : nullptr);
    if (!module.get() || !type.get()) SPELLpythonHelper::instance().checkError();
    if (!PyType_Check(type.get()))
        THROW_EXCEPTION("Cannot inspect dictionary", "Native DataContainer type unavailable", SPELL_ERROR_LANGUAGE);
    return PyObject_TypeCheck(dict, reinterpret_cast<PyTypeObject*>(type.get()));''')
    # Validate requested chunk indexes before touching the vector.
    start = text.index('void SPELLrequestProcessor::processGetDictionary(')
    finish = text.index('bool SPELLrequestProcessor::isDataContainer(', start)
    section = text[start:finish]
    before = '''		int chunkNo = STRI( msg.get( MessageField::FIELD_CHUNK ) );'''
    assert section.count(before) == 1
    section = section.replace(before, '''        const std::string encoded = msg.get(MessageField::FIELD_CHUNK);
        size_t chunkNo = 0;
        auto parsed = std::from_chars(encoded.data(), encoded.data()+encoded.size(), chunkNo);
        if (parsed.ec != std::errc() || parsed.ptr != encoded.data()+encoded.size() || chunkNo >= m_valueChunks.size())
        {
            response = SPELLipcHelper::createErrorResponse(ExecutorMessages::RSP_GET_DICTIONARY, msg);
            response.set(MessageField::FIELD_ERROR, "Invalid dictionary chunk");
            response.set(MessageField::FIELD_FATAL, PythonConstants::False);
            return;
        }''')
    section = section.replace('std::string contents = "";', 'm_valueChunks.clear();\n        std::string contents = "";')
    begin = section.index('\t\t\tint numChunks = contents.size()/VALUE_CHUNK_SIZE;')
    end = section.index('\t\t\tDEBUG("Total "', begin)
    section = section[:begin] + '''            // IPC fields carry UTF-8 text. Never split a code point between
            // messages: JSON clients must decode each chunk independently.
            size_t offset = 0;
            while (offset < contents.size())
            {
                size_t end = std::min(offset + size_t(VALUE_CHUNK_SIZE), contents.size());
                while (end < contents.size() && (static_cast<unsigned char>(contents[end]) & 0xC0) == 0x80)
                    --end;
                m_valueChunks.push_back(contents.substr(offset, end-offset));
                offset = end;
            }
''' + section[end:]
    text = text[:start] + section + text[finish:]
    # This list is a new reference; each native Var remains owned by the list's
    # container dictionary, and getValueEx returns a new Python value reference.
    begin = text.index('\t\telse if ( isDataContainer(dict) )')
    end = text.index('\t\telse if ( SPELLpythonHelper::instance().isDatabase(dict) )', begin)
    body = text[begin:end]
    body = body.replace('PyObject* keyList = containerObj->container->getKeys();',
                        'SPELLpython313::Owned keyList(containerObj->container->getKeys());')
    body = body.replace('PyList_Size(keyList)', 'PyList_Size(keyList.get())')
    body = body.replace('PyList_GetItem(keyList,index)', 'PyList_GetItem(keyList.get(),index)')
    body = body.replace('std::string valueStr = PYSSTR(var->getValueEx());',
                        'SPELLpython313::Owned rawValue(var->getValueEx());\n                std::string valueStr = PYSSTR(rawValue.get());')
    text = text[:begin] + body + text[end:]
    begin = text.index('void SPELLrequestProcessor::processUpdateDictionary(')
    text = text[:begin] + UPDATE
    return text.encode('utf-8')


UPDATE = '''void SPELLrequestProcessor::processUpdateDictionary( const SPELLipcMessage& msg, SPELLipcMessage& response )
{
    SPELLmonitor mon(m_requestLock);
    response.setId(ExecutorMessages::RSP_UPD_DICTIONARY);
    SPELLsafePythonOperations operations("SPELLrequestProcessor::processUpdateDictionary");
    auto reject = [&](const std::string& error) {
        PyErr_Clear();
        response = SPELLipcHelper::createErrorResponse(ExecutorMessages::RSP_UPD_DICTIONARY, msg);
        response.set(MessageField::FIELD_ERROR, error);
        response.set(MessageField::FIELD_REASON, "");
        response.set(MessageField::FIELD_FATAL, PythonConstants::False);
    };
    try
    {
        const std::string name = msg.get(MessageField::FIELD_DICT_NAME);
        SPELLpython313::Owned dictionary(Py_XNewRef(SPELLexecutor::instance().getVariableManager().getVariableRef(name)));
        PyObject* dict = dictionary.get();
        if (!dict) throw std::invalid_argument("Dictionary does not exist");
        const bool data = isDataContainer(dict);
        const bool database = !data && SPELLpythonHelper::instance().isDatabase(dict);
        if (!data && !database && !PyDict_Check(dict))
            throw std::invalid_argument("Unsupported dictionary type");
        const std::string encoded = msg.get(MessageField::FIELD_DICT_CONTENTS);
        if (encoded.size() > 65536) throw std::invalid_argument("Dictionary value exceeds 64 KiB");
        std::vector<std::string> fields;
        const std::string delimiter = VARIABLE_PROPERTY_SEPARATOR_STR;
        size_t position = 0;
        while (true)
        {
            size_t separator = encoded.find(delimiter, position);
            fields.push_back(encoded.substr(position, separator == std::string::npos ? separator : separator-position));
            if (separator == std::string::npos) break;
            position = separator + delimiter.size();
        }
        if (fields.size() != (data ? 4u : 2u) || fields[0].empty() || fields[1].empty())
            throw std::invalid_argument("Malformed dictionary edit fields");
        SPELLpython313::Owned key(PyUnicode_FromStringAndSize(fields[0].data(), fields[0].size()));
        if (!key.get()) SPELLpythonHelper::instance().checkError();
        if (data)
        {
            auto* container = reinterpret_cast<SPELLdtaContainerObject*>(dict)->container;
            if (!container) throw std::invalid_argument("Uninitialized DataContainer");
            const std::string merge = msg.get(MessageField::FIELD_DICT_MERGENEW);
            if (!merge.empty() && merge != "True" && merge != "true" && merge != "False" && merge != "false")
                throw std::invalid_argument("Invalid merge flag");
            const bool exists = container->hasKey(key.get());
            if (!exists && merge != "True" && merge != "true")
                throw std::invalid_argument("Variable does not exist in the data container");
            std::string format = fields[2];
            if (format == "NONE" || format == LanguageConstants::DEC) format.clear();
            if (!format.empty() && format != LanguageConstants::BIN && format != LanguageConstants::HEX && format != LanguageConstants::OCT)
                throw std::invalid_argument("Invalid integer format");
            if (fields[3] != "True" && fields[3] != "true" && fields[3] != "False" && fields[3] != "false")
                throw std::invalid_argument("Invalid confirmation flag");
            // Retain the original Development expression semantics, after the
            // entire request and target key have passed structural validation.
            SPELLpython313::Owned value(SPELLpythonHelper::instance().eval(fields[1], false));
            if (!value.get()) SPELLpythonHelper::instance().checkError();
            SPELLdtaVariable* variable = nullptr;
            if (exists)
                variable = reinterpret_cast<SPELLdtaVariableObject*>(PyDict_GetItem(container->getDict(), key.get()))->var;
            const std::string type = variable ? variable->getType() : "";
            if (!format.empty() && type != LanguageConstants::LONG &&
                !(type.empty() && PyLong_Check(value.get()) && !PyBool_Check(value.get())))
                throw std::invalid_argument("Integer format requires a LONG variable");
            struct Notifications
            {
                SPELLdtaContainer* container;
                bool enabled;
                bool global;
                explicit Notifications(SPELLdtaContainer* target): container(target), enabled(target->areNotificationsEnabled()),
                    global(SPELLdtaContainer::areGlobalnotificationsEnabled())
                {
                    container->setNotificationsEnabled(false);
                    // A newly merged Var has no parent until construction ends.
                    // Its constructor must not synchronously notify this same
                    // IPC request thread while the edit is being processed.
                    SPELLdtaContainer::setGlobalNotificationsEnabled(false);
                }
                ~Notifications()
                {
                    SPELLdtaContainer::setGlobalNotificationsEnabled(global);
                    container->setNotificationsEnabled(enabled);
                }
            } notifications(container);
            if (variable)
                variable->setValue(value.get()); // direct validation, no procedure prompt
            else
            {
                container->setValue(key.get(), value.get());
                variable = reinterpret_cast<SPELLdtaVariableObject*>(PyDict_GetItem(container->getDict(), key.get()))->var;
            }
            variable->setFormat(format);
            variable->setConfirmGet(fields[3] == "True" || fields[3] == "true");
        }
        else
        {
            SPELLpython313::Owned value(SPELLpythonHelper::instance().eval(fields[1], false));
            if (!value.get()) SPELLpythonHelper::instance().checkError();
            if (PyObject_SetItem(dict, key.get(), value.get()) < 0) SPELLpythonHelper::instance().checkError();
        }
    }
    catch (const SPELLcoreException& error) { reject(error.what()); }
    catch (const std::exception& error) { reject(error.what()); }
}
'''
