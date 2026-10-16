"""Execute the exact scheduler callback with a pending interrupted timer tick."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import wait_interrupt_patches as patch

PRELUDE=r'''
#include <atomic>
#include <functional>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>
#define DEBUG(value) do {} while(false)
enum { STATUS_WAITING, STATUS_INTERRUPTED };
struct SPELLmutex {
    std::recursive_mutex value;
    void lock(){value.lock();} void unlock(){value.unlock();}
    bool trylock(){return value.try_lock();}
};
struct SPELLtime {
    int n;
    SPELLtime():n(10){} SPELLtime(int n,int,bool):n(n){}
    void setCurrent(){n=10;} int getSeconds()const{return n;}
    std::string toString()const{return std::to_string(n);}
    SPELLtime operator-(const SPELLtime& x)const{return SPELLtime(n-x.n,0,true);}
    bool operator>(const SPELLtime& x)const{return n>x.n;}
    bool operator>=(const SPELLtime& x)const{return n>=x.n;}
    bool operator<=(const SPELLtime& x)const{return n<=x.n;}
};
struct SPELLsafePythonOperations {explicit SPELLsafePythonOperations(const char*){}};
namespace LanguageConstants { const int SCOPE_PROC=0; }
struct Controller {int status=STATUS_WAITING; int getStatus(){return status;}};
struct Cif {int writes=0; void write(const std::string&,int){++writes;}};
struct SPELLexecutor {
    Controller controller; Cif cif;
    static SPELLexecutor& instance(){static SPELLexecutor value;return value;}
    Controller& getController(){return controller;} Cif& getCIF(){return cif;}
};
struct SPELLscheduleCondition {
    enum {SCH_TIME,SCH_PROMPT,SCH_EXPRESSION,SCH_CHILD,SCH_VERIFICATION};
    int type=SCH_VERIFICATION; std::string message="progress";
    std::vector<SPELLtime> interval{SPELLtime(1,0,true)};
};
struct SPELLscheduler {
    SPELLmutex m_checkLock;
    bool m_abortTimer=false;
    SPELLscheduleCondition m_condition;
    SPELLtime m_notificationPeriod{1,0,true},m_lastNotificationTime{0,0,true},m_checkTargetTime{20,0,true};
    unsigned m_notificationPeriodIndex=0;
    int checks=0,finished=0; bool fail=false,complete=false;
    bool check(){++checks;if(fail)throw std::runtime_error("probe");return complete;}
    bool checkTime(){return check();} bool checkExpression(){return check();}
    bool checkChildProcedure(){return check();} bool checkVerification(){return check();}
    void finishWait(bool,bool){++finished;}
    bool timerCallback(unsigned long);
};
'''

MAIN=r'''
int main(){
    auto& executor=SPELLexecutor::instance();
    int pausedChecks=0,pausedMessages=0,activeChecks=0,activeMessages=0,completion=0;
    for(int kind : {SPELLscheduleCondition::SCH_TIME,SPELLscheduleCondition::SCH_EXPRESSION,
                   SPELLscheduleCondition::SCH_CHILD,SPELLscheduleCondition::SCH_VERIFICATION}){
        SPELLscheduler scheduler;scheduler.m_condition.type=kind;
        executor.controller.status=STATUS_INTERRUPTED;executor.cif.writes=0;
        scheduler.timerCallback(200);
        pausedChecks+=scheduler.checks;pausedMessages+=executor.cif.writes;
        scheduler.checks=0;executor.cif.writes=0;
        executor.controller.status=STATUS_WAITING;
        scheduler.timerCallback(200);activeChecks+=scheduler.checks;activeMessages+=executor.cif.writes;
        scheduler.complete=true;scheduler.timerCallback(400);completion+=scheduler.finished;
    }
    bool aborted=false,exceptionReleased=false,contendedQuiet=false;
    {SPELLscheduler scheduler;scheduler.m_abortTimer=true;
     aborted=scheduler.timerCallback(200)&&scheduler.finished==1&&scheduler.checks==0;}
    {SPELLscheduler scheduler;scheduler.fail=true;
     try{scheduler.timerCallback(200);}catch(const std::runtime_error&){}
     std::thread observer([&]{exceptionReleased=scheduler.m_checkLock.trylock();
         if(exceptionReleased)scheduler.m_checkLock.unlock();});observer.join();
     if(!exceptionReleased)scheduler.m_checkLock.unlock();}
    {SPELLscheduler scheduler;executor.cif.writes=0;scheduler.m_checkLock.lock();
     std::thread observer([&]{scheduler.timerCallback(200);});observer.join();
     scheduler.m_checkLock.unlock();contendedQuiet=scheduler.checks==0&&executor.cif.writes==0;}
    std::cout<<"{\"paused_checks\":"<<pausedChecks<<",\"paused_messages\":"<<pausedMessages
        <<",\"active_checks\":"<<activeChecks<<",\"active_messages\":"<<activeMessages
        <<",\"completion\":"<<completion<<",\"aborted\":"<<(aborted?"true":"false")
        <<",\"exception_released\":"<<(exceptionReleased?"true":"false")
        <<",\"contended_quiet\":"<<(contendedQuiet?"true":"false")<<"}\n";
    return pausedChecks==0&&pausedMessages==0&&activeChecks==4&&activeMessages==4&&completion==4
        &&aborted&&exceptionReleased&&contendedQuiet ? 0:1;
}
'''


def method(source):
    text=source.decode();start=text.index('bool SPELLscheduler::timerCallback(')
    return text[start:text.index('//=============================================================================',start)]


def main():
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=False)
    ported=Path('/source',patch.SOURCE).read_bytes()
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        original=archive.read(patch.SOURCE)
    patched=patch.apply(patch.SOURCE,original,ported)
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    report=dict(passed=False,preimage_sha256=sha(ported),patched_sha256=sha(patched),probes={})
    for label,source in (('original',ported),('patched',patched)):
        probe=output/(label+'-probe.cpp');probe.write_text(PRELUDE+method(source)+MAIN,encoding='utf-8')
        binary=output/(label+'-probe')
        build=subprocess.run(['c++','-std=c++17','-pthread','-Wall','-Wextra','-Wno-unused-parameter',str(probe),'-o',str(binary)],capture_output=True)
        (output/(label+'-build.log')).write_bytes(build.stdout+build.stderr)
        assert build.returncode==0,build.stderr.decode()
        run=subprocess.run([str(binary)],capture_output=True,timeout=10)
        (output/(label+'-run.log')).write_bytes(run.stdout+run.stderr)
        observed=json.loads(run.stdout)
        assert run.returncode==(1 if label=='original' else 0)
        assert observed['paused_checks']==(4 if label=='original' else 0)
        assert observed['paused_messages']==(4 if label=='original' else 0)
        assert observed['active_checks']==4 and observed['completion']==4 and observed['aborted']
        assert observed['exception_released'] is (label=='patched')
        assert observed['contended_quiet'] is (label=='patched')
        report['probes'][label]=dict(exit_code=run.returncode,observation=observed,
            source_sha256=sha(probe.read_bytes()),binary_sha256=sha(binary.read_bytes()))
    report.update(passed=True,scope='Exact callback control-flow probe; actual native IPC validation remains required')
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
