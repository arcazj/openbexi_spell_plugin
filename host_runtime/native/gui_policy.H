// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_GUI_POLICY_H
#define OPENBEXI_V08_GUI_POLICY_H
#include <stdexcept>

static int v08_next_gui_key(int& last, int proposed)
{
    // This private Context never reconnects or reuses a transport identity.
    // A copied key cannot displace the host, even after its TCP socket closes.
    if (proposed != 0 || last >= 1024)
        throw std::runtime_error("Native GUI reconnect/capacity denied");
    return ++last;
}
#endif
