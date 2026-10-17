"""Keep explicitly empty display/event messages distinct from an idle buffer."""
import hashlib

SOURCE = 'lib/SPELL_CIFS/src/SPELLdisplayBuffer.C'
PREIMAGES = {SOURCE: 'fae984f867c8d76df6fa90c8ce004ce7412b3f8d97b9c84fb684fbb8f3694403'}


def apply(name, source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest() != PREIMAGES[name]:
        raise ValueError('Empty event buffer preimage differs: '+name)
    text = source.decode('utf-8')
    # A severity is assigned for every queued message, including an empty one.
    # Empty messages flush separately so coalescing cannot erase their identity.
    assert text.count('if (m_text != "")') == 6
    text = text.replace('if (m_text != "")', 'if (m_severity != "")')
    before = '\tSPELLmonitor m(m_lock);\n\t// If there is already data'
    assert text.count(before) == 4
    text = text.replace(before, '\tSPELLmonitor m(m_lock);\n'
        '\tif (msg.empty()) flush();\n\t// If there is already data')
    before = '\tm_scope = scope;\n}'
    assert text.count(before) == 4
    text = text.replace(before, '\tm_scope = scope;\n\tif (msg.empty()) flush();\n}')
    return text.encode('utf-8')
