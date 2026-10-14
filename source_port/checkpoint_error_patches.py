"""Checked original frame-manager exception unwind audit/correction.

SPDX-License-Identifier: GPL-3.0-or-later
The continuation engine's synchronous/thread-owned frame guard is unchanged.
"""
import hashlib

SOURCE = 'lib/SPELL_EXC/src/SPELLframeManager.C'
ORIGINAL = 'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402'
PORTED = '31e1b73109a6266817f26ea0d1ad67935d81854c9e34c314aab75b33bda41fcf'


def apply(name, original, ported, *, audit=False, fix=False):
    assert name == SOURCE
    assert hashlib.sha256(original).hexdigest() == ORIGINAL
    assert hashlib.sha256(ported).hexdigest() == PORTED
    assert audit or fix
    source = ported.decode()
    if fix:
        marker = ('void SPELLframeManager::callbackEventLine'
            '( PyFrameObject* frame, const std::string& file, const int line, const std::string& name )\n{\n')
        assert source.count(marker) == 1
        source = source.replace(marker, marker + '''    // Preserve the original error stack while an exception is still unwinding.
    // A LINE in a known ancestor proves that execution has resumed there. Only
    // then retire skipped exceptional returns before the recorder snapshots it.
    // Uncaught errors have no such LINE and retain their existing error models.
    if (m_inError && m_currentFrame != frame)
    {
        bool knownAncestor = false;
        for (const auto& key : m_modelKeys)
        {
            auto model = m_modelMap.find(key);
            if (model != m_modelMap.end() && model->second->getFrame() == frame)
            {
                knownAncestor = true;
                break;
            }
        }
        if (knownAncestor)
        {
            while (m_currentFrame != frame && m_modelKeys.size() > 1)
            {
                m_inError = false;
                try
                {
                    callbackEventReturn(m_currentFrame, file, line, name);
                }
                catch (...)
                {
                    m_inError = true;
                    throw;
                }
                m_inError = true;
            }
        }
    }
''')
    if audit:
        source = '#include <iostream>\n' + source
        for event in ('Call','Line','Return','Error'):
            marker = ('void SPELLframeManager::callbackEvent'+event+
                '( PyFrameObject* frame, const std::string& file, const int line, const std::string& name )\n{\n')
            assert source.count(marker) == 1
            source = source.replace(marker, marker + '''    std::cerr << "[CHECKPOINT_FRAME_AUDIT] event='''+event+''' frame=" << frame
        << " tracked=" << m_currentFrame << " model=" << (m_model ? m_model->getFrame() : nullptr)
        << " in_error=" << m_inError << " name=" << name << " line=" << line << std::endl;
''')
    return source.encode()
