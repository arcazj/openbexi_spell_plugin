// Test dependency fixtures; terminal CIF/controller bodies and IPC are production.
#include <string>
#include <map>
#include <mutex>
#include <iostream>
#include <cassert>
#include <stdexcept>
#include <cstdlib>
#include <nlohmann/json.hpp>
#define OPENBEXI_V08_TERMINALS 1
#define DEBUG(x) do {} while (false)
#define LOG_INFO(x) do {} while (false)
#define LOG_ERROR(x) do {} while (false)
#define LOG_WARN(x) do {} while (false)
using std::string;
const string CMD_ABORT="CMD_ABORT",CMD_FINISH="CMD_FINISH",CMD_INTERRUPT="CMD_INTERRUPT",
 CMD_PAUSE="CMD_PAUSE",CMD_CLOSE="CMD_CLOSE",CMD_ACTION="CMD_ACTION",CMD_STEP="CMD_STEP",
 CMD_STEP_OVER="CMD_STEP_OVER",CMD_RUN="CMD_RUN",CMD_SKIP="CMD_SKIP",CMD_GOTO="CMD_GOTO",
 CMD_SCRIPT="CMD_SCRIPT",CMD_RELOAD="CMD_RELOAD",CMD_RECOVER="CMD_RECOVER",CMD_RESOURCES="CMD_RESOURCES";
namespace ExecutorMessages {const string MSG_CMD_ABORT="CMD_ABORT",MSG_CMD_CLOSE="CMD_CLOSE";}
namespace LanguageConstants {const int SCOPE_SYS=1;}
const int MSG_TYPE_ONEWAY=1;
static nlohmann::json effects={{"cancel_calls",0},{"prompt_cancelled",0},{"closing",0},
 {"abort",0},{"close",0},{"start_processing",0},{"dispatch",0},{"denied",0}};
struct ExecutorCommand {string id,arg,earg,v08Request;bool v08External=false;};
struct SPELLipcMessage {
 string id;int type=1;std::map<string,string> fields;
 string getId()const{return id;}int getType()const{return type;}
 string get(const string& k)const{auto i=fields.find(k);return i==fields.end()?"":i->second;}
 const std::map<string,string>& v08Fields()const{return fields;}
};
struct SPELLmonitor {std::lock_guard<std::mutex> guard;explicit SPELLmonitor(std::mutex& m):guard(m){}};
struct Mailbox {void commandProcessed(){}};
struct ResourceManager {void callResourceMonitorFromClient(const string&) {}};
class SPELLserverCif {
 public:
 std::mutex m_ipcLock;bool prompt=false;
 string getProcId()const{return "main#1";}
 bool cancelPrompt(){effects["cancel_calls"]=int(effects["cancel_calls"])+1;
   if(prompt){effects["prompt_cancelled"]=int(effects["prompt_cancelled"])+1;prompt=false;return true;}
   return false;}
 void setClosing(){effects["closing"]=int(effects["closing"])+1;}
 void error(const string&,int){}
 void v08ProcessTerminal(const SPELLipcMessage&);
};
class SPELLcontroller {
 public:
 string m_procId="main#1";bool m_recover=false,m_reload=false;Mailbox m_mailbox;
 bool isCommandPending(){return false;}
 void startCommandProcessing(){effects["start_processing"]=int(effects["start_processing"])+1;}
 void doAbort(){effects["abort"]=int(effects["abort"])+1;}
 void doClose(){effects["close"]=int(effects["close"])+1;}
 void doFinish(){}void doUserAction(){}void doStep(bool){}void doPlay(){}void doSkip(){}
 void doGoto(int){}void doGoto(const string&){}void doPause(){}void doInterrupt(){}
 void doScript(const string&,bool){}void doReload(){}void doRecover(){}
 void notifyCommandToCore(const string&){}void setCommandFinished(){}
 void executeCommand(const ExecutorCommand&);
};
int STRI(const string& text){return std::stoi(text);}
static SPELLserverCif cif;static SPELLcontroller controller;
class SPELLexecutor {
 ResourceManager resources;
 public:
 static SPELLexecutor& instance(){static SPELLexecutor value;return value;}
 SPELLserverCif& getCIF(){return cif;}ResourceManager& getResourceManager(){return resources;}
 void command(const ExecutorCommand& cmd,bool){effects["dispatch"]=int(effects["dispatch"])+1;controller.executeCommand(cmd);}
};
#include "execution_gate.H"
static void v08_note_disabled_mutation(const string&,const string&) noexcept {
 effects["denied"]=int(effects["denied"])+1;
}
#include "composed_terminal_methods.inc"
int main() {
 assert(v08_request_supported("REQ_EXEC_STATUS"));
 assert(v08_message_disabled("CMD_STOP",false));
 string line;std::cout<<"READY"<<std::endl;std::getline(std::cin,line);
 auto in=nlohmann::json::parse(line);SPELLipcMessage msg;
 msg.id=in.at("command");msg.type=in.value("type",1);
 msg.fields=in.at("fields").get<std::map<string,string>>();cif.prompt=in.value("prompt",false);
 if(in.value("direct",false)){
   ExecutorCommand cmd;cmd.id=msg.id;cmd.v08External=true;cmd.v08Request=msg.get("V08ControlRequest");
   controller.executeCommand(cmd);
 } else {
   cif.v08ProcessTerminal(msg);
   if(in.value("duplicate",false))cif.v08ProcessTerminal(msg);
 }
 std::cout<<effects.dump()<<std::endl;
 return 0;
}
