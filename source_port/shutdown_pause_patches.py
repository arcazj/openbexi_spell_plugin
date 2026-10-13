"""Cancel an already active forced pause when its native executor is closing.

SPDX-License-Identifier: GPL-3.0-or-later
The ordinary waitStatus API and its deadline semantics are unchanged.
"""
import hashlib

SOURCE = 'lib/SPELL_CTX/src/SPELLexecutor.C'
ORIGINAL = '63db5c0e063e08ad4fea0bcd4c66efb53b205beb6218a226c6ab7573ae677d32'
PORTED = '59809d4d3d333207b5d3def831b6e8572d3ad20a1cd36298baa18ed7893ccee2'

BEFORE = r'''void SPELLexecutor::forcePause()
{
    if (m_closing) return;
	ExecutorCommand cmd;
	if (getStatus() == STATUS_WAITING)
	{
		cmd.id = CMD_INTERRUPT;
		LOG_WARN("Interrupting procedure (force stop)");
		command(cmd);
		bool timedout = waitStatus(STATUS_INTERRUPTED, 5*1000);
		if (timedout)
		{
			LOG_ERROR("Unable to interrupt procedure");
			return;
		}
		LOG_WARN("Procedure interrupted");
	}
	else if (getStatus() == STATUS_RUNNING)
	{
		if (m_executorStatusEvent.isClear())
			return;
		cmd.id = CMD_PAUSE;
		LOG_WARN("Pausing procedure (force stop)");
		command(cmd);
		bool timedout = waitStatus(STATUS_PAUSED, 5*1000);
		if (timedout)
		{
			LOG_ERROR("Unable to pause procedure");
			return;
		}
		LOG_WARN("Procedure paused");
	}
}'''

AFTER = r'''void SPELLexecutor::forcePause()
{
    const auto stopping = [this]() {
        const SPELLprocessStatus state = m_processStatus.load();
        return m_closing.load() || state == PSTATUS_FINISHED
            || state == PSTATUS_FAILED || state == PSTATUS_KILLED;
    };
    if (stopping()) return;
    ExecutorCommand cmd;
    SPELLexecutorStatus target;
    const char* failure;
    const char* success;
    if (getStatus() == STATUS_WAITING)
    {
        cmd.id = CMD_INTERRUPT;
        target = STATUS_INTERRUPTED;
        failure = "Unable to interrupt procedure";
        success = "Procedure interrupted";
        LOG_WARN("Interrupting procedure (force stop)");
    }
    else if (getStatus() == STATUS_RUNNING)
    {
        if (m_executorStatusEvent.isClear()) return;
        cmd.id = CMD_PAUSE;
        target = STATUS_PAUSED;
        failure = "Unable to pause procedure";
        success = "Procedure paused";
        LOG_WARN("Pausing procedure (force stop)");
    }
    else return;
    if (stopping()) return;
    command(cmd);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    for (;;)
    {
        // Arm before reading state. Close/process-finished do not signal this
        // event, so bounded waits also observe their atomic cancellation flags.
        // Do not report cancellation as reaching the requested status.
        m_executorStatusEvent.clear();
        if (stopping())
        {
            LOG_INFO("Forced pause cancelled: executor closing or stopped");
            return;
        }
        if (getStatus() == target)
        {
            LOG_WARN(success);
            return;
        }
        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline)
        {
            if (stopping())
            {
                LOG_INFO("Forced pause cancelled: executor closing or stopped");
                return;
            }
            LOG_ERROR(failure);
            return;
        }
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(deadline-now).count();
        m_executorStatusEvent.wait(static_cast<unsigned long>(remaining < 49 ? remaining+1 : 50));
    }
}'''


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != ORIGINAL
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected original or ported context executor source')
    text = ported.decode('utf-8')
    if text.count(BEFORE) != 1:
        raise ValueError('Unexpected forced-pause implementation')
    return text.replace(BEFORE, AFTER).encode('utf-8')
