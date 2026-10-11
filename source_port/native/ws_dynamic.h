// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsStorage.H"
#include "SPELL_WS/SPELLwsStartupInfo.H"
// Original dynamic-data role, with one owned modern frame snapshot in place of
// removed PyTryBlock, f_valuestack and fast-locals arrays.
class SPELLwsDynamicData {
public:
    SPELLwsDynamicData(const SPELLwsStartupInfo&,unsigned int,PyFrameObject*);
    ~SPELLwsDynamicData();
    void reset();
    void save();
    void update();
    void refresh();
    PyFrameObject* recover(); // new inspection view; never an evaluation frame
    void restore();
    void cleanup();
    void rebind(PyFrameObject* frame) { m_frame = frame; }
    void setState(PyObject* state);
    PyObject* getState() const { return m_state; } // borrowed
private:
    SPELLwsStartupInfo m_startup;
    PyFrameObject* m_frame; // borrowed from SPELLwsFrame
    PyObject* m_state;
    PyObject* m_handled;
    std::string m_persistentFile, m_recoveryFile;
    unsigned int m_depth;
};
#endif
