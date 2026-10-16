"""Resolve native child identifiers and header NAME using configured folder order."""
import hashlib

SOURCE='lib/SPELL_EXC/src/SPELLchildManager.C'
PREIMAGES={SOURCE:'10696aa78e422601589c291c0d2f7bae0890190651e6639ca08d69cca33b050b'}


def apply(name,source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Procedure-library native preimage differs: '+name)
    text=source.decode('utf-8')
    first=text.index('    // We assume that the list is ordered by priorities already')
    last=text.index('    if (suitableProc == "")',first)
    replacement='''    std::string suitableProc;
    const char* configured = std::getenv("OPENBEXI_SPELL_LIBRARY_PRIORITIES");
    std::vector<std::string> priorities;
    if (configured && *configured)
        priorities = SPELLutils::tokenize(configured, std::string(1, '\\x1f'));
    std::size_t selectedRank = priorities.size() + 1;
    for (const std::string& entry : procList)
    {
        const std::size_t separator = entry.find('|');
        const std::string identifier = entry.substr(0, separator);
        const std::string name = separator == std::string::npos ? "" : entry.substr(separator+1);
        const std::size_t slash = identifier.find_last_of('/');
        const std::string leaf = slash == std::string::npos ? identifier : identifier.substr(slash+1);
        // An explicit library path always selects that exact procedure.
        if (procId.find('/') != std::string::npos && procId == identifier)
        {
            suitableProc = identifier;
            break;
        }
        if (procId != leaf && procId != name && procId != identifier) continue;
        std::size_t rank = priorities.size();
        for (std::size_t index=0; index<priorities.size(); ++index)
        {
            const std::string prefix = priorities[index] + "/";
            if (identifier.compare(0, prefix.size(), prefix) == 0)
            {
                rank = index;
                break;
            }
        }
        // The original procedure inventory supplies deterministic tie order.
        if (rank < selectedRank)
        {
            suitableProc = identifier;
            selectedRank = rank;
        }
    }
'''
    text=text[:first]+replacement+text[last:]
    return ('#include <cstdlib>\n'+text).encode('utf-8')
