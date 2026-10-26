// SPDX-License-Identifier: GPL-3.0-or-later
// Frozen composed SPELLprocess::popen; SES ENGINEERING with Python port signal handling.
#include "SPELL_PRC/SPELLprocessManager.H"
pid_t SPELLprocess::popen( std::string command )
{
	/** \todo define and use the pipes for process output */
    pid_t pid;
	DEBUG("[PRC] POpen prefork");
    pid = fork();

    if (pid < 0)
    {
        return pid;
    }
    else if (pid == 0)
    {
        sigset_t termination;
        sigemptyset(&termination);
        for (int value : {SIGINT,SIGTERM,SIGHUP,SIGQUIT}) sigaddset(&termination,value);
        if (sigprocmask(SIG_UNBLOCK,&termination,nullptr)!=0) _exit(127);
        execl("/bin/bash", "bash", "-c", command.c_str(), nullptr);
        // Only async-signal-safe operations between fork and exec/_exit.
        const char failure[]="SPELL child exec failed\n";
        write(STDERR_FILENO,failure,sizeof(failure)-1);
        _exit(127);
    }
    return pid;
}

//=============================================================================
