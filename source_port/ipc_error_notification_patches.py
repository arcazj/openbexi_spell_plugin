"""Route original asynchronous executor errors before response correlation."""
import hashlib

SOURCE = 'lib/SPELL_IPC/src/SPELLipcInput.C'
PREIMAGES = {SOURCE: '91c045628cf34f8e8782295cc9dbe62fe38dc3545381300b9032edb2503929a0'}


def apply(name, source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest() != PREIMAGES[name]:
        raise ValueError('IPC error notification preimage differs: '+name)
    before = b'''    case MSG_TYPE_RESPONSE:
    case MSG_TYPE_ERROR:
        m_interface.incomingResponse(msg);
        break;'''
    after = b'''    case MSG_TYPE_RESPONSE:
        m_interface.incomingResponse(msg);
        break;
    case MSG_TYPE_ERROR:
        // SPELLserverCif emits MSG_ERROR/STATUS asynchronously. Its independent
        // sequence can equal a pending request: never offer it to the mailbox.
        // Genuine error replies lack the STATUS data type and remain responses.
        if (msg.getId() == "MSG_ERROR" && msg.get("DataType") == "STATUS")
            m_interface.incomingMessage(msg);
        else
            m_interface.incomingResponse(msg);
        break;'''
    if source.count(before) != 1:
        raise ValueError('IPC error routing anchor differs')
    return source.replace(before, after)
