"""Checked original context compatibility with the real continuation WSP format.

SPDX-License-Identifier: GPL-3.0-or-later
Composes after the checked DATA context correction; ASRUN lookup and the
recorder's integrity/source/runtime validation remain authoritative.
"""
import hashlib

SOURCE = 'lib/SPELL_CTX/src/SPELLcontext.C'
ORIGINAL = 'cf4576a8a95c543cddd53b8cb4f136a53e0114c1fc5bf3ebd6e39b1c0ff9129c'
PORTED = '9618798e11004db0d42422b16806c3a7fbe0c53ebbe8a2bba05fa5e410940b81'

BEFORE = r'''void SPELLcontext::checkRecoveryFiles( const std::string& filename )
{
	SPELLcontextConfig& ctxConfig = SPELLconfiguration::instance().getContext(m_config.contextName);

	std::string wsDataDir = SPELLutils::getSPELL_DATA() + PATH_SEPARATOR + ctxConfig.getLocationPath("ws");
	std::string arDataDir = SPELLutils::getSPELL_DATA() + PATH_SEPARATOR + ctxConfig.getLocationPath("ar");

	bool wsdFound = false;
	bool wssFound = false;
	bool wspFound = false;
	bool arfFound = false;

	std::list<std::string> files = SPELLutils::getFilesInDir(wsDataDir);
	for(std::list<std::string>::const_iterator it = files.begin(); it != files.end(); it++)
	{
		std::string completeFilename = *it;
		std::string path = wsDataDir + PATH_SEPARATOR + completeFilename;
		if (completeFilename.find(filename) != std::string::npos)
		{
			if (!wssFound && + (completeFilename.find(".wss") != std::string::npos))
			{
				wssFound = true;
				if (SPELLutils::fileSize(path)==0)
				{
					THROW_EXCEPTION("Recovery file check failed", "WSS data file has zero bytes", SPELL_ERROR_WSTART);
				}
			}
			else if (!wsdFound && + (completeFilename.find(".wsd") != std::string::npos))
			{
				wsdFound = true;
				if (SPELLutils::fileSize(path)==0)
				{
					THROW_EXCEPTION("Recovery file check failed", "WSD data file has zero bytes", SPELL_ERROR_WSTART);
				}
			}
			if (!wspFound && + (completeFilename.find(".wsp") != std::string::npos))
			{
				wspFound = true;
				if (SPELLutils::fileSize(path)==0)
				{
					THROW_EXCEPTION("Recovery file check failed", "WSP data file has zero bytes", SPELL_ERROR_WSTART);
				}
			}
		}
	}
	if (!wssFound || !wsdFound || !wspFound)
	{
		THROW_EXCEPTION("Recovery file check failed", "Warmstart files missing", SPELL_ERROR_WSTART);
	}
'''

AFTER = r'''void SPELLcontext::checkRecoveryFiles( const std::string& filename )
{
    // The controller supplies the checkpoint stem, never a filesystem path.
    // Match an exact basename instead of accepting a substring of another run.
    if (filename.empty() || filename == "." || filename == ".."
        || filename.find_first_of("/\\") != std::string::npos)
    {
        THROW_EXCEPTION("Recovery file check failed", "Invalid recovery basename", SPELL_ERROR_WSTART);
    }
    for (std::string::const_iterator it = filename.begin(); it != filename.end(); ++it)
    {
        const unsigned char value = static_cast<unsigned char>(*it);
        if (value < 32 || value == 127)
        {
            THROW_EXCEPTION("Recovery file check failed", "Invalid recovery basename", SPELL_ERROR_WSTART);
        }
    }
    SPELLcontextConfig& ctxConfig = SPELLconfiguration::instance().getContext(m_config.contextName);
    std::string wsDataDir = SPELLutils::getSPELL_DATA() + PATH_SEPARATOR + ctxConfig.getLocationPath("ws");
    std::string arDataDir = SPELLutils::getSPELL_DATA() + PATH_SEPARATOR + ctxConfig.getLocationPath("ar");
    bool wspFound = false;
    bool arfFound = false;
    // The CPython continuation recorder writes one versioned WSP envelope.
    // Its reader still verifies format, CRC, payload and source/runtime identity.
    // Obsolete WSS/WSD companions are neither produced nor required.
    std::list<std::string> files = SPELLutils::getFilesInDir(wsDataDir);
    for (std::list<std::string>::const_iterator it = files.begin(); it != files.end(); ++it)
    {
        if (*it == filename + ".wsp")
        {
            wspFound = true;
            if (SPELLutils::fileSize(wsDataDir + PATH_SEPARATOR + *it) == 0)
            {
                THROW_EXCEPTION("Recovery file check failed", "WSP data file has zero bytes", SPELL_ERROR_WSTART);
            }
            break;
        }
    }
    if (!wspFound)
    {
        THROW_EXCEPTION("Recovery file check failed", "WSP data file missing", SPELL_ERROR_WSTART);
    }'''


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != ORIGINAL
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected original or composed context recovery source')
    text = ported.decode('utf-8')
    if text.count(BEFORE) != 1:
        raise ValueError('Unexpected original context recovery block')
    return text.replace(BEFORE, AFTER).encode('utf-8')
