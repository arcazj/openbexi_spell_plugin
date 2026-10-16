// SPDX-License-Identifier: GPL-3.0-or-later
// Hooks only schedule the real mailbox code; queues and locks are unmodified.
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <thread>
#include <cassert>

std::mutex gate;
std::condition_variable changed;
bool armed=false, readerHolding=false, writerHolding=false;
bool removeStarted=false, readerFinished=false, releaseWriter=false;
void mailbox_test_after_retrieve_lookup() {
    if (!armed) return;
    std::unique_lock<std::mutex> lock(gate);
    readerHolding=true; changed.notify_all();
    assert(changed.wait_for(lock,std::chrono::seconds(5),[]{return writerHolding;}));
}
void mailbox_test_after_writer_lookup() {
    if (!armed) return;
    std::unique_lock<std::mutex> lock(gate);
    writerHolding=true; changed.notify_all();
    assert(changed.wait_for(lock,std::chrono::seconds(5),[]{return releaseWriter;}));
}
void mailbox_test_before_remove() {
    if (!armed) return;
    std::lock_guard<std::mutex> lock(gate);
    removeStarted=true; changed.notify_all();
}
#include "mailbox-tested.C"
class Mailbox: public SPELLipcMessageMailbox {
public:
    Mailbox():SPELLipcMessageMailbox("race-test"){}
    using SPELLipcMessageMailbox::prepare;
    using SPELLipcMessageMailbox::place;
};
int main(int argc,char** argv) {
    Mailbox mailbox;
    mailbox.prepare("request");
    assert(mailbox.place("request",SPELLipcMessage("first")));
#ifndef MAILBOX_BASELINE
    assert(!mailbox.place("request",SPELLipcMessage("duplicate")));
    mailbox.cancel("request"); // Already queued response must win without a wait.
#endif
    assert(mailbox.retrieve("request",1000).getId()=="first");
    assert(!mailbox.place("request",SPELLipcMessage("late")));
    mailbox.cancel("request");
    mailbox.prepare("race");
    assert(mailbox.place("race",SPELLipcMessage("seed")));
    armed=true;
    std::thread reader([&]{
        assert(mailbox.retrieve("race",1000).getId()=="seed");
        std::lock_guard<std::mutex> lock(gate);
        readerFinished=true;changed.notify_all();
    });
    {
        std::unique_lock<std::mutex> lock(gate);
        assert(changed.wait_for(lock,std::chrono::seconds(5),[]{return readerHolding;}));
    }
    std::thread writer([&]{
        if (argc>1 && std::string(argv[1])=="cancel") mailbox.cancel("race");
        else mailbox.place("race",SPELLipcMessage("late-duplicate"));
    });
    bool removedWhileWriterHeld;
    {
        std::unique_lock<std::mutex> lock(gate);
        assert(changed.wait_for(lock,std::chrono::seconds(5),[]{return removeStarted;}));
        removedWhileWriterHeld=changed.wait_for(lock,std::chrono::milliseconds(200),[]{return readerFinished;});
        releaseWriter=true; changed.notify_all();
    }
    writer.join(); reader.join();
    assert(!removedWhileWriterHeld);
    armed=false;
    assert(!mailbox.place("race",SPELLipcMessage("after-removal")));
    std::cout << "mailbox lifetime, duplicate, cancellation and late reply: PASS\n";
}
