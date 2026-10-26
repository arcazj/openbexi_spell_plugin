// SPDX-License-Identifier: GPL-3.0-or-later
// Frozen SPELLprocess::popen, SES ENGINEERING (2008, 2018).
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
        if (execl("/bin/bash", "bash", "-c", command.c_str(), NULL) != 0)
		{
        	std::cerr << "####################################################################" << std::endl;
        	std::cerr << "####################################################################" << std::endl;
        	std::cerr << "[FATAL] Unable to start process, errno " << errno << std::endl;
        	std::cerr << "####################################################################" << std::endl;
        	std::cerr << "####################################################################" << std::endl;
		}
        exit(1);
    }
    return pid;
}

//=============================================================================
