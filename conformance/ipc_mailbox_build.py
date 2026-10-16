"""Compile the queue lifetime fix and deterministic original/fixed race probes."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import ipc_mailbox_patches as patch
from incremental_native import rebuild

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
output=Path('/ipc-mailbox-patch')
output.mkdir()
shutil.copytree('/ipc-recipe', output/'recipes', ignore=shutil.ignore_patterns('__pycache__'))
source=Path('/source')/patch.SOURCE
original=source.read_bytes()
patched=patch.apply(original)
record={'passed':False,'source':patch.SOURCE,'preimage_sha256':hashlib.sha256(original).hexdigest(),'patched_sha256':hashlib.sha256(patched).hexdigest(),'probes':{},'full_release_accepted':False}
for label,content in [('original',original),('patched',patched)]:
    folder=output/label
    folder.mkdir()
    (folder/'source.C').write_bytes(content)
    text=content.decode()
    # Force the reader to hold the queue before the competing producer looks it
    # up. The producer then pauses while that reader attempts queue removal.
    needle='SPELLipcMessageQueue* queue = getQueue(id);'
    text=text.replace(needle,needle+'\n    mailbox_test_after_retrieve_lookup();',1)
    text=text.replace('        remove(id);','        mailbox_test_before_remove();\n        remove(id);',1)
    for signature in ('void SPELLipcMessageMailbox::cancel(', 'bool SPELLipcMessageMailbox::place('):
        start=text.index(signature)
        end=text.index('\n}',start)+2
        body=text[start:end]
        body,count=re.subn(r'(SPELLipcMessageQueue\* queue = [^;]+;)',r'\1\n    mailbox_test_after_writer_lookup();',body,count=1)
        assert count==1,signature
        text=text[:start]+body+text[end:]
    (folder/'mailbox-tested.C').write_text(text)
    shutil.copyfile('/ipc-recipe/ipc_mailbox_race.cpp',folder/'probe.cpp')
    command=['c++','-std=c++17','-g','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-I/source/include','-I/usr/local/include/python3.13',str(folder/'probe.cpp'),'-L/out','-lspell_executor313','-Wl,-rpath,/out','-L/usr/local/lib','-lpython3.13','-llog4cplus','-o',str(folder/'probe')]
    if label=='original':command.insert(1,'-DMAILBOX_BASELINE')
    subprocess.run(command,check=True)
    for operation in ('place','cancel'):
        run=subprocess.run([str(folder/'probe'),operation],capture_output=True,timeout=20)
        log=folder/(operation+'.log')
        log.write_bytes(run.stdout+run.stderr)
        if label=='original':
            assert run.returncode!=0 and b'AddressSanitizer: heap-use-after-free' in log.read_bytes(),log
        else:
            assert run.returncode==0 and b'PASS' in run.stdout and b'AddressSanitizer:' not in log.read_bytes(),log
        record['probes'][label+'-'+operation]={'exit_code':run.returncode,'log_sha256':sha(log)}
        print(label,operation,run.returncode,flush=True)
source.write_bytes(patched)
compiled=rebuild([patch.SOURCE],output/'compiled')
record.update(passed=True,artifacts={n:r['sha256'] for n,r in compiled['artifacts'].items()},original_artifacts={n:r['original_sha256'] for n,r in compiled['artifacts'].items()},recipes={p.name:sha(p) for p in Path('/ipc-recipe').iterdir() if p.is_file()})
(output/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
