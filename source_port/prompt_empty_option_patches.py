"""Convert a declared empty prompt option to its native zero-based index."""
import hashlib

SOURCE = 'lib/SPELL_CIF/src/SPELLcifHelper.C'
PREIMAGES = {SOURCE: 'a97e1ae8d36c7c0945a37d3a511acc3fc8fe225a4f395de3d92378eeb6c92060'}


def apply(name, source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest() != PREIMAGES[name]:
        raise ValueError('Empty prompt option preimage differs: '+name)
    signature = b'std::string SPELLcifHelper::getRawAnswer('
    if source.count(signature) != 1:
        raise ValueError('Native raw-answer function is not unique')
    prefix, body = source.split(signature)
    before = b'if (answer != "")'
    after = (b'if (answer != "" || std::find(def.expected.begin(), '
             b'def.expected.end(), answer) != def.expected.end())')
    if body.count(before) != 1:
        raise ValueError('Native empty-answer guard differs')
    return prefix + signature + body.replace(before, after)
