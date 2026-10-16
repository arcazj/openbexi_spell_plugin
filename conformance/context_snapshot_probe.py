"""Force the actual listener methods to interleave across port/status reads."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import context_snapshot_patches as patch

PRELUDE = r'''
#include <chrono>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#define DEBUG(value) do {} while(false)
#define ISTR(value) std::to_string(value)
#define STRI(value) std::stoi(value)
static std::mutex spellListenerContextState;
namespace MessageField {
const std::string FIELD_CTX_NAME="name", FIELD_CTX_PORT="port", FIELD_CTX_STATUS="status",
FIELD_CTX_DRV="driver", FIELD_CTX_SC="sc", FIELD_CTX_FAM="family", FIELD_CTX_GCS="gcs",
FIELD_CTX_DESC="description", FIELD_CTX_MAXPROC="maxproc";
}
namespace MessageValue { const std::string DATA_CTX_RUNNING="RUNNING"; }
namespace ListenerMessages { const std::string MSG_CONTEXT_OP="context-operation"; }
const int MSG_TYPE_ONEWAY=0;
struct SPELLcontextConfig {
    std::string getDriverName(){return "driver";} std::string getSC(){return "sc";}
    std::string getFamily(){return "family";} std::string getGCS(){return "gcs";}
    std::string getDescription(){return "description";}
};
struct SPELLdriverConfig {int getMaxProcs(){return 4;}};
struct SPELLipcMessage {
    std::map<std::string,std::string> fields;
    std::function<void()> afterPort;
    SPELLipcMessage()=default;
    void set(const std::string& key,const std::string& value) {
        fields[key]=value;
        if (key==MessageField::FIELD_CTX_PORT && afterPort) afterPort();
    }
    std::string get(const std::string& key) const {return fields.at(key);}
    int getKey() const {return 7;}
    void setId(const std::string&){} void setType(int){}
    void setSender(const std::string&){} void setReceiver(const std::string&){}
};
struct Event {void set(){}};
struct Peer {void displace(const SPELLipcMessage*){} void displace(const SPELLipcMessage&){} };
class SPELLlistenerContext {
public:
    struct ContextInfo {
        int m_key=0; std::string m_name; unsigned short m_port=0; std::string m_status;
        SPELLcontextConfig* m_ctxConfig; SPELLdriverConfig* m_drvConfig;
    };
    std::map<std::string,ContextInfo> m_openContexts;
    Event m_waitForContextStart;
    Peer gui; Peer* m_gui=&gui; Peer* m_peer=nullptr;
    SPELLcontextConfig config; SPELLdriverConfig driver;
    SPELLlistenerContext() {
        m_openContexts["example"]={0,"example",0,"AVAILABLE",&config,&driver};
    }
    void fillContextInfo(const std::string, SPELLipcMessage&);
    void onNewContext(const SPELLipcMessage&);
};
'''

MAIN = r'''
int main() {
    SPELLlistenerContext context;
    SPELLipcMessage login, response;
    login.set(MessageField::FIELD_CTX_NAME,"example");
    login.set(MessageField::FIELD_CTX_PORT,"45393");
    std::promise<void> portRead, updateEntered, updateFinished;
    auto read=portRead.get_future();
    auto entered=updateEntered.get_future();
    auto finished=updateFinished.get_future();
    bool updateCompletedDuringRead=false;
    std::thread writer([&] {
        read.wait();
        updateEntered.set_value();
        context.onNewContext(login);
        updateFinished.set_value();
    });
    response.afterPort=[&] {
        portRead.set_value();
        entered.wait();
        updateCompletedDuringRead=(finished.wait_for(std::chrono::seconds(2))==std::future_status::ready);
    };
    context.fillContextInfo("example",response);
    writer.join();
    SPELLipcMessage subsequent, missing;
    context.fillContextInfo("example",subsequent);
    context.fillContextInfo("missing",missing);
    const bool coherent=response.get("status")!="RUNNING" || response.get("port")=="45393";
    const bool recovered=subsequent.get("status")=="RUNNING" && subsequent.get("port")=="45393";
    const bool absent=missing.get("status")=="ERROR" && missing.get("port")=="0";
    std::cout << "{\"port\":\"" << response.get("port") << "\",\"status\":\""
        << response.get("status") << "\",\"update_completed_during_read\":"
        << (updateCompletedDuringRead?"true":"false") << ",\"coherent\":"
        << (coherent?"true":"false") << ",\"subsequent_current\":"
        << (recovered?"true":"false") << ",\"unknown_context_rejected\":"
        << (absent?"true":"false") << "}\n";
    return coherent && recovered && absent ? 0 : 1;
}
'''


def methods(source):
    text = source.decode('utf-8')
    blocks = []
    for name in ('fillContextInfo', 'onNewContext'):
        start = text.index('void SPELLlistenerContext::' + name + '(')
        end = text.index('//=============================================================================', start)
        blocks.append(text[start:end])
    return '\n'.join(blocks)


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    ported = native_patches.apply(patch.SOURCE, original)
    patched = patch.apply(patch.SOURCE, original, ported)
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    report = dict(passed=False, source=patch.SOURCE,
        preimage_sha256=digest(ported), patched_sha256=digest(patched), probes={})
    for label, source in (('original', ported), ('patched', patched)):
        (output / (label + '.C')).write_bytes(source)
        probe = output / (label + '-probe.cpp')
        probe.write_text(PRELUDE + methods(source) + MAIN, encoding='utf-8', newline='\n')
        binary = output / (label + '-probe')
        build = subprocess.run(['c++', '-std=c++17', '-pthread', '-Wall', '-Wextra',
            '-Werror', str(probe), '-o', str(binary)], capture_output=True)
        (output / (label + '-build.log')).write_bytes(build.stdout + build.stderr)
        assert build.returncode == 0, build.stderr.decode()
        run = subprocess.run([str(binary)], capture_output=True, timeout=10)
        (output / (label + '-run.log')).write_bytes(run.stdout + run.stderr)
        observation = json.loads(run.stdout)
        assert run.returncode == (1 if label == 'original' else 0)
        assert observation['subsequent_current'] and observation['unknown_context_rejected']
        assert observation['coherent'] is (label == 'patched')
        assert observation['update_completed_during_read'] is (label == 'original')
        report['probes'][label] = dict(exit_code=run.returncode, observation=observation,
            source_sha256=digest(probe.read_bytes()), binary_sha256=digest(binary.read_bytes()))
    report['passed'] = True
    report['scope'] = 'Controlled exact listener-method interleaving; native IPC acceptance remains required'
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
