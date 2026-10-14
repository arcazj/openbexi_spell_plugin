// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the original context-side executor model; replace only its wire
// command dispatch so native wait entry and concurrent close are deterministic.
// Each scenario is a separate process. Its uninitialized IPC model lives until
// process exit; no teardown/ownership claim is made by this focused wait probe.
// The unchanged full context gate separately exercises actual IPC teardown.
#include "SPELL_CTX/SPELLexecutor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include <atomic>
#include <chrono>
#include <functional>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

using Clock = std::chrono::steady_clock;
using Millis = std::chrono::milliseconds;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

class PauseProbe final : public SPELLexecutor {
public:
    using SPELLexecutor::forcePause;
    using SPELLexecutor::processFinished;
    std::atomic_int commands{0};
    std::atomic_bool dispatched{false};
    std::string last;
    bool complete = false;
    PauseProbe(): SPELLexecutor(SPELLexecutorStartupParams("pause#1", "2000-01-01_000000"), nullptr) {
        processStarted("pause#1");
    }
    void publish(const std::string& status) {
        SPELLipcMessage notification("model-status");
        notification.setType(MSG_TYPE_NOTIFY_ASYNC);
        notification.set(MessageField::FIELD_DATA_TYPE, MessageValue::DATA_TYPE_STATUS);
        notification.set(MessageField::FIELD_EXEC_STATUS, status);
        executorNotification(notification);
    }
    void command(const ExecutorCommand& command) override {
        ++commands;
        last = command.id;
        if (complete) publish(command.id == CMD_INTERRUPT ? "INTERRUPTED" : "PAUSED");
        dispatched = true;
    }
};

void awaitDispatch(PauseProbe& probe) {
    const auto deadline = Clock::now() + std::chrono::seconds(2);
    while (!probe.dispatched && Clock::now() < deadline) std::this_thread::sleep_for(Millis(1));
    require(probe.dispatched, "Forced-pause command was not dispatched");
}

void cancellation(const char* status, bool finished) {
    PauseProbe& probe = *new PauseProbe;
    probe.publish(status);
    auto active = std::async(std::launch::async, [&] { probe.forcePause(); });
    awaitDispatch(probe);
    std::this_thread::sleep_for(Millis(30));
    require(active.wait_for(Millis(0)) != std::future_status::ready, "Wait was not active before cancellation");
    const auto started = Clock::now();
    if (finished) probe.processFinished("pause#1", 0);
    else probe.beginClose();
    const bool ready = active.wait_for(Millis(800)) == std::future_status::ready;
    active.get(); // Preserve and drain baseline's full timeout before destroying the original model.
    require(ready, "Active forced pause did not cancel within 800ms");
    require(Clock::now() - started < Millis(900), "Cancellation completed too late");
    require(probe.commands == 1, "Cancellation sent another command");
    require(probe.getStatus() != STATUS_PAUSED && probe.getStatus() != STATUS_INTERRUPTED,
            "Cancellation fabricated the target executor status");
}

int main(int argc, char** argv) {
    require(argc == 2, "Select exactly one scenario");
    const std::string selected = argv[1];
    int total = 0, failures = 0;
    auto test = [&](const char* name, std::function<void()> body) {
        if (selected != name) return;
        ++total;
        try { body(); std::cout << "CASE " << name << " PASS" << std::endl; }
        catch (const SPELLcoreException& error) {
            ++failures; std::cout << "CASE " << name << " FAIL " << error.what() << std::endl;
        } catch (const std::exception& error) {
            ++failures; std::cout << "CASE " << name << " FAIL " << error.what() << std::endl;
        }
    };
    test("already-closing", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("RUNNING"); probe.beginClose();
        probe.forcePause(); require(probe.commands == 0, "Already closing executor received pause");
    });
    test("already-finished", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("RUNNING"); probe.processFinished("pause#1", 0);
        probe.forcePause(); require(probe.commands == 0, "Finished process received pause");
    });
    test("pause-reached", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("RUNNING"); probe.complete = true;
        probe.forcePause(); require(probe.commands == 1 && probe.last == CMD_PAUSE,
                                   "Expected one native pause command");
        require(probe.getStatus() == STATUS_PAUSED, "Pause did not reach real model status");
    });
    test("interrupt-reached", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("WAITING"); probe.complete = true;
        probe.forcePause(); require(probe.commands == 1 && probe.last == CMD_INTERRUPT,
                                   "Expected one native interrupt command");
        require(probe.getStatus() == STATUS_INTERRUPTED, "Interrupt did not reach real model status");
    });
    test("close-during-pause", [] { cancellation("RUNNING", false); });
    test("close-during-interrupt", [] { cancellation("WAITING", false); });
    test("finish-during-pause", [] { cancellation("RUNNING", true); });
    test("finish-during-interrupt", [] { cancellation("WAITING", true); });
    test("real-timeout-with-noise", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("RUNNING");
        auto active = std::async(std::launch::async, [&] { probe.forcePause(); });
        awaitDispatch(probe);
        const auto started = Clock::now();
        std::thread noise([&] {
            for (int n = 0; n < 100; ++n) {
                probe.publish("RUNNING");
                std::this_thread::sleep_for(Millis(10));
            }
        });
        active.get(); noise.join();
        const auto elapsed = Clock::now() - started;
        require(elapsed >= Millis(4500) && elapsed < Millis(6500), "Native five-second timeout changed");
        require(probe.commands == 1 && probe.getStatus() == STATUS_RUNNING,
                "Timeout fabricated a status or repeated a command");
    });
    test("ordinary-wait-unchanged", [] {
        PauseProbe& probe = *new PauseProbe; probe.publish("RUNNING"); probe.beginClose();
        const auto started = Clock::now();
        require(probe.waitStatus(STATUS_PAUSED, 70), "General waitStatus treated closing as success");
        require(Clock::now() - started >= Millis(60), "General waitStatus deadline changed");
    });
    require(total == 1, "Unknown scenario");
    std::cout << "{\"tests\":" << total << ",\"failures\":" << failures << "}" << std::endl;
    return failures ? 1 : 0;
}
