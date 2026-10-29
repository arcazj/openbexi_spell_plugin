"""Keep startup ACK routing behind the existing Context registry publication."""
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib


def method(text, signature):
    start = text.index(signature)
    brace = text.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def patch_startup_ack_tree(source):
    client = source / "lib/SPELL_CTX/src/SPELLclient.C"
    manager = source / "lib/SPELL_CTX/src/SPELLexecutorManager.C"
    header = source / "include/SPELL_CTX/SPELLexecutorManager.H"
    client_text, manager_text, header_text = (
        client.read_text(),
        manager.read_text(),
        header.read_text(),
    )
    expected = {
        "void SPELLclient::processMessageFromClient(": "e839685f88176e758c756b89b13de8620800ff5c58611f775daf417a36aa4a1b",
        "void SPELLexecutorManager::startExecutor(": "c9f9141748f5ef487841e3735d557e949b1d711ee7566861f272b8a6ec25cb40",
        "void SPELLexecutorManager::recoverExecutor(": "17f3032593e47ae5e66d0818cf0c1df8d813d0901e0283e3b957f8aff3b44461",
    }
    for signature, digest in expected.items():
        text = client_text if "SPELLclient::" in signature else manager_text
        if hashlib.sha256(method(text, signature).encode()).hexdigest() != digest:
            raise ValueError("Native startup ACK preimage differs: " + signature)
    old = method(client_text, "void SPELLclient::processMessageFromClient(")
    new = (
        old.replace(
            "\t\tSPELLexecutor* exec = SPELLexecutorManager::instance().getExecutor(procId);\n",
            "",
        )
        .replace(
            "\t\t\tif (exec->getControllingClient() != this)\n\t\t\t{\n\t\t\t\treturn;\n\t\t\t}\n",
            "            SPELLexecutorManager::instance().acknowledgeExecutor(msg, this);\n"
            "            return;\n",
        )
        .replace(
            "\t\texec->sendMessageToExecutor(msg);",
            "        SPELLexecutor* exec = SPELLexecutorManager::instance().getExecutor(procId);\n"
            "\t\texec->sendMessageToExecutor(msg);",
        )
    )
    declaration = "SPELLexecutor* getExecutor( const std::string& procId );"
    if header_text.count(declaration) != 1:
        raise ValueError("Native startup ACK manager declaration differs")
    header_text = header_text.replace(
        declaration,
        declaration
        + "\n\n        void acknowledgeExecutor(const SPELLipcMessage& msg, SPELLclient* client);",
    )
    manager_text += """
// Startup publishes the model only after process login and identity binding.
// A notification may already be on the GUI channel in that interval. Serialize
// its ACK with the existing registry owner, without publishing a partial model
// or admitting an execution command. Failed startup still leaves no ACK target.
void SPELLexecutorManager::acknowledgeExecutor(const SPELLipcMessage& msg, SPELLclient* client)
{
    if (msg.getId() != ExecutorMessages::ACKNOWLEDGE) return;
    SPELLmonitor registry(m_lock);
    SPELLexecutor* exec = getExecutor(msg.get(MessageField::FIELD_PROC_ID));
    if (exec->getControllingClient() != client) return;
    exec->sendMessageToExecutor(msg);
}
"""
    client.write_text(client_text.replace(old, new))
    manager.write_text(manager_text)
    header.write_text(header_text)
