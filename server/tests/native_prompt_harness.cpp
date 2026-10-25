// Test-only native substrate. Original patched CIF methods are appended by pytest.
// Transport/scheduler doubles are explicit; this is not the full interpreter.
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <functional>
#include <cerrno>

struct TestJson {
    std::map<std::string, TestJson> object;
    std::string value;
    bool null = false, mapping = false;
    TestJson(std::nullptr_t) : null(true) {}
    TestJson(const char* text) : value(text) {}
    TestJson(const std::string& text) : value(text) {}
    TestJson(const std::map<std::string, std::string>& items) : mapping(true) {
        for (const auto& item : items) object.emplace(item.first, TestJson(item.second));
    }
    TestJson(std::initializer_list<std::pair<const std::string, TestJson>> items)
        : object(items), mapping(true) {}
    std::string dump() const {
        if (null) return "null";
        auto quote = [](const std::string& in) {
            std::ostringstream out; out << '"';
            for (unsigned char c : in) {
                if (c == '"' || c == '\\') out << '\\' << c;
                else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c);
                else out << c;
            }
            out << '"'; return out.str();
        };
        if (!mapping) return quote(value);
        std::string result = "{"; bool first = true;
        for (const auto& item : object) {
            if (!first) result += ',';
            first = false; result += quote(item.first) + ':' + item.second.dump();
        }
        return result + '}';
    }
};
namespace nlohmann { using json = TestJson; }
// Only the system-call transport is replaced. Production prompt_gate.H and
// source-derived CIF methods below are compiled and executed unchanged.
#define OPENBEXI_V08_ADMISSION_IPC_H
static std::mutex rpcLock;
static std::atomic<int> denials{0};
static void v08_native_request(const TestJson& request) {
    std::lock_guard<std::mutex> guard(rpcLock);
    std::cout << request.dump() << std::endl;
    std::string ack;
    if (!std::getline(std::cin, ack) || ack != "ALLOW")
        throw std::runtime_error("controlled native transport denial or reply loss");
}
static void v08_note_disabled_mutation(const std::string&, const std::string&) { ++denials; }
static constexpr int MSG_TYPE_ONEWAY = 1;
struct SPELLipcMessage {
    std::string id;
    int type = MSG_TYPE_ONEWAY;
    std::map<std::string, std::string> fields;
    SPELLipcMessage() = default;
    explicit SPELLipcMessage(const std::string& name) : id(name) {}
    std::string getId() const { return id; }
    void setId(const std::string& value) { id = value; }
    bool isVoid() const { return id.empty(); }
    void setType(int value) { type = value; }
    int getType() const { return type; }
    std::string get(const std::string& key) const {
        auto p = fields.find(key); return p == fields.end() ? "" : p->second;
    }
    void set(const std::string& key, const std::string& value) { fields[key] = value; }
    bool hasField(const std::string& key) const { return fields.count(key); }
    const std::map<std::string, std::string>& v08Fields() const { return fields; }
};
static const SPELLipcMessage VOID_MESSAGE;
namespace MessageId {
const std::string MSG_ID_PROMPT_START="MSG_PROMPT_START", MSG_ID_PROMPT_END="MSG_PROMPT_END";
const std::string MSG_ID_PROMPT_ANSWER="MSG_ANSWER", MSG_ID_CANCEL="MSG_CANCEL";
}
namespace MessageField { const std::string FIELD_RVALUE="ReturnValue"; }
namespace LanguageConstants { const int SCOPE_SYS=1; }
#define LOG_WARN(x) do {} while(0)
#define SPELL_ERROR_EXECUTION 14
#define THROW_EXCEPTION(a,b,c) throw std::runtime_error(b)
struct SPELLsafeThreadOperations { explicit SPELLsafeThreadOperations(const char*) {} };
struct SPELLtime {
    long long us = 600000;
    long long getSeconds() const { return us/1000000; }
    long long getMilliseconds() const { return (us%1000000)/1000; }
    long long getMicroseconds() const { return us%1000; }
};
struct Definition { SPELLtime timeout; bool defaultProvided=true; std::string defaultAnswer="default"; };
struct Config { std::string getControlClient() const { return "host"; } bool isHeadless() const { return false; } };
struct Scheduler {
    std::atomic<int> started{0}, finished{0}, cancelled{0};
    void startPrompt(const SPELLtime&, bool) { ++started; }
    void finishPrompt() { ++finished; }
    void cancelPrompt() { std::this_thread::sleep_for(std::chrono::milliseconds(5)); ++cancelled; }
};
struct SPELLexecutor {
    Scheduler scheduler;
    static SPELLexecutor& instance() { static SPELLexecutor v; return v; }
    Scheduler& getScheduler() { return scheduler; }
};
struct SPELLcifHelper {
    static std::string getRawAnswer(const std::string& answer, const Definition&) { return answer; }
};
#include "mutation_policy.H"
#include "prompt_gate.H"
static std::mutex spellPromptTransitionLock;
class SPELLserverCif {
public:
    std::mutex m_promptAnswerLock;
    std::condition_variable m_promptAnswerReady;
    bool m_promptPending=false;
    SPELLipcMessage m_promptAnswer, m_promptMessage;
    Definition m_promptDef;
    V08PromptState m_v08Prompt;
    std::string getProcId() const { return "main#1"; }
    Config getExecutorConfig() { return Config{}; }
    void sendGUIMessage(const SPELLipcMessage&) {}
    void sendGUIMessage(const SPELLipcMessage*) {}
    void warning(const char*, int) {}
    void startPrompt();
    bool cancelPrompt();
    bool cancelPrompt(const SPELLipcMessage*);
    void waitPromptAnswer();
    void processPrompt(const SPELLipcMessage& msg);
};
// SOURCE_DERIVED_METHODS
