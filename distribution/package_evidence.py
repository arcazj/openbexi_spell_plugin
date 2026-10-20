"""Retain hash-bound release evidence and source inputs without rewriting reports."""
import argparse,collections,contextlib,hashlib,io,json,re,subprocess,tarfile,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SHA=re.compile(r'[0-9a-f]{64}');REV=re.compile(r'[0-9a-f]{7,40}')
def digest(body):return hashlib.sha256(body).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seed',action='append',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--audit-only',action='store_true')
parser.add_argument('--historical-gaps',type=Path)
args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
pending=collections.deque((str(p.resolve()),None,None,'seed') for p in args.seed)
seen=set();files={};blobs={};issues=[];runtime_paths=set();source_cache={};history_cache={};expanded=set();commits=set();deferred_sources={}
worktrees=[Path(line[9:]) for line in subprocess.check_output(['git','worktree','list','--porcelain'],cwd=ROOT,text=True).splitlines() if line.startswith('worktree ')]
manifest=dict(schema='openbexi.spell.portable-evidence/1',files=files,issues=issues,
 scope='Hash-verified reports, referenced files, available native captures and source inputs. Explicit unavailable old diagnostic source bytes are listed in historical_source_gaps. Member names are content hashes; original path/commit names remain in this manifest. No historical report is rewritten.')
archive_path=output/'openbexi-spell-v0.6-evidence.tar.gz'
historical=[]
allowed={} if args.historical_gaps is None else {
 (row['path'],row['expected'],row['origin']):row
 for row in json.loads(args.historical_gaps.read_bytes())['sources']}

def store(name,expected,body=None,path=None,kind='file',commit=None):
 actual=digest(body) if body is not None else file_sha(path)
 assert expected is None or actual==expected,(name,expected,actual)
 key=(str(commit)+':'+name if commit else name)+'@'+actual
 if actual not in blobs:
  member='sha256/'+actual
  if body is None:
   size=path.stat().st_size;info=tarfile.TarInfo(member);info.size=size;info.mode=0o644
   if archive is not None:
    with path.open('rb') as stream:archive.addfile(info,stream)
  else:
   size=len(body);info=tarfile.TarInfo(member);info.size=size;info.mode=0o644
   if archive is not None:archive.addfile(info,io.BytesIO(body))
  blobs[actual]=dict(member=member,bytes=size)
 files[key]=dict(path=name,sha256=actual,kind=kind,**blobs[actual])
 if commit:files[key]['commit']=commit;commits.add(commit)
 return actual

def source(name,expected,origin,commit,retry=False):
 key=(name,expected)
 if key in source_cache:return
 if expected in blobs:
  files[(str(commit)+':'+name if commit else name)+'@'+expected]=dict(path=name,sha256=expected,kind='source-input',**blobs[expected],**(dict(commit=commit) if commit else {}))
  source_cache[key]=True;return
 if key in deferred_sources and not retry:return
 if name.startswith('/'):
  runtime_paths.add(name);return
 p=Path(origin);candidates=[ROOT/'.qualification/recovered-historical-sources'/expected,p.parent/'inputs'/name,p.parent/'source'/name,p.parent/name]
 parts=p.parts
 if '.qualification' in parts:candidates.append(Path(*parts[:parts.index('.qualification')])/name)
 candidates.append(ROOT/name)
 candidates.extend(ROOT/folder/name for folder in ('source_port','driver_plugin','host_runtime','host_plugin','shared_plugin','conformance','distribution'))
 for candidate in candidates:
  if candidate.is_file() and file_sha(candidate)==expected:
   store(name,expected,path=candidate,kind='source-input');source_cache[key]=True;return
 aliases=[name,*[folder+'/'+name for folder in ('source_port','conformance','distribution','driver_plugin','host_runtime','host_plugin','shared_plugin')]]
 for alias in aliases:
  revisions=[]
  if commit:revisions.append(commit)
  if alias not in history_cache:
   history_cache[alias]=subprocess.check_output(['git','log','--all','--format=%H','--',alias],cwd=ROOT,text=True).splitlines()
  revisions.extend(history_cache[alias])
  for revision in dict.fromkeys(revisions):
   result=subprocess.run(['git','show',revision+':'+alias],cwd=ROOT,capture_output=True)
   if result.returncode:continue
   body=result.stdout
   if digest(body)==expected:
    store(name,expected,body=body,kind='source-input',commit=revision)
    files[revision+':'+name+'@'+expected]['repository_path']=alias
    source_cache[key]=True;return
   # Historical Windows captures sometimes bind CRLF checkouts of LF Git blobs.
   crlf=body.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
   if digest(crlf)==expected:
    store(name,expected,body=crlf,kind='source-input-crlf',commit=revision)
    files[revision+':'+name+'@'+expected]['repository_path']=alias
    source_cache[key]=True;return
 deferred_sources[(name,expected)]=(origin,commit)

def walk(value,origin,commit=None):
 if isinstance(value,dict):
  for key,item in value.items():
   if (key.endswith('commit') or key.endswith('revision') or key=='commit') and isinstance(item,str) and re.fullmatch(r'[0-9a-f]{40}',item):commits.add(item)
  revision=next((value.get(k) for k in ('source_revision','source_commit','commit') if isinstance(value.get(k),str) and REV.fullmatch(value[k])),commit)
  if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str) and SHA.fullmatch(value['sha256']):
   pending.append((value['path'],value['sha256'],revision,origin))
   for key,companion in (('workspace_sha256','workspace.tar'),('native_logs_archive_sha256','workspace.tar'),('junit_sha256','junit.xml')):
    if key in value:pending.append((str(Path(value['path']).parent/companion),value[key],None,origin))
  if isinstance(value.get('report'),str) and isinstance(value.get('sha256'),str) and SHA.fullmatch(value['sha256']):
   pending.append((value['report'],value['sha256'],None,origin))
  if isinstance(value.get('raw_report_path'),str) and isinstance(value.get('raw_report_sha256'),str):
   pending.append((value['raw_report_path'],value['raw_report_sha256'],None,origin))
  for key,child in value.items():
   if key in ('inputs','source_inputs') and isinstance(child,dict):
    for name,expected in child.items():
     if isinstance(expected,str) and SHA.fullmatch(expected):source(name,expected,origin,revision)
   elif key!='lf_normalized_inputs':walk(child,origin,revision)
 elif isinstance(value,list):
  for child in value:walk(child,origin,commit)

with (contextlib.nullcontext(None) if args.audit_only else tarfile.open(archive_path,'w:gz',compresslevel=5)) as archive:
 while pending:
  name,expected,commit,origin=pending.popleft()
  identity=(name,expected,commit)
  if identity in seen:continue
  seen.add(identity)
  if name.startswith('/'):
   runtime_paths.add(name);continue
  path=Path(name);actual_path=(ROOT/path).resolve();body=None;use_git=False
  try:
   if not path.is_absolute() and '.qualification' in path.parts and (not actual_path.is_file() or (expected is not None and file_sha(actual_path)!=expected)):
    options=[base/path for base in worktrees]
    actual_path=next((p.resolve() for p in options if p.is_file() and (expected is None or file_sha(p)==expected)),actual_path)
   if actual_path.is_file() and (expected is None or file_sha(actual_path)==expected):
    actual=store(str(actual_path),expected,path=actual_path)
    if path.suffix.lower()=='.json':body=actual_path.read_bytes()
   elif commit and not path.is_absolute():
    body=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT,stderr=subprocess.PIPE)
    store(name,expected,body=body,commit=commit,kind='git-file');use_git=True
   else:raise ValueError('Missing or changed referenced file: '+str(actual_path))
   if name.endswith('.json'):
    record=json.loads(body)
    # Raw case captures retain their complete surrounding workspace, including
    # SQLite journals, protobuf packets, transcripts, binary outputs and inputs.
    if not use_git and '.qualification' in actual_path.parts and isinstance(record,dict) and isinstance(record.get('checks'),dict):
     folder=actual_path.parent
     if folder not in expanded:
      expanded.add(folder)
      for capture in sorted(folder.rglob('*')):
       if capture.is_file() and not any(p in ('__pycache__','.pytest_cache') for p in capture.parts) and capture.suffix!='.pyc':
        store(str(capture),None,path=capture,kind='capture')
    walk(record,str(actual_path),commit if use_git else None)
   if len(seen)%25==0:print('Verified references:',len(seen),'unique blobs:',len(blobs),flush=True)
  except Exception as error:
   issues.append(dict(path=name,expected=expected,commit=commit,origin=origin,error=str(error)))
 for (name,expected),(origin,commit) in deferred_sources.items():
  source(name,expected,origin,commit,retry=True)
  if (name,expected) not in source_cache:
   row=allowed.get((name,expected,origin))
   if row is not None and file_sha(Path(origin))==row['origin_sha256']:
    historical.append(row)
   else:issues.append(dict(path=name,expected=expected,commit=commit,origin=origin,error='Source input unavailable after complete capture traversal'))
 manifest.update(passed=not issues,unique_blobs=len(blobs),uncompressed_bytes=sum(v['bytes'] for v in blobs.values()),runtime_paths=sorted(runtime_paths),commits=sorted(commits),historical_source_gaps=historical)
 encoded=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(encoded);info.mode=0o644
 if archive is not None:archive.addfile(info,io.BytesIO(encoded))
(output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
verified=0
if args.audit_only:
 result=dict(passed=not issues,audit_only=True,files=len(files),unique_blobs=len(blobs),uncompressed_bytes=manifest['uncompressed_bytes'],issues=issues,historical_source_gaps=historical)
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(result),flush=True)
 raise SystemExit(bool(issues))
with tarfile.open(archive_path,'r:gz') as archive:
 for member in archive:
  if member.name=='MANIFEST.json':continue
  assert member.isfile() and member.name.startswith('sha256/')
  h=hashlib.sha256()
  with archive.extractfile(member) as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
  assert h.hexdigest()==member.name.removeprefix('sha256/')
  verified+=1
assert verified==len(blobs)
result=dict(passed=not issues,archive=dict(path=str(archive_path),sha256=file_sha(archive_path),bytes=archive_path.stat().st_size),manifest=dict(path=str(output/'MANIFEST.json'),sha256=file_sha(output/'MANIFEST.json')),files=len(files),unique_blobs=verified,issues=issues,historical_source_gaps=historical)
(output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in result.items() if k!='issues'}),flush=True)
for issue in issues[:10]:print(json.dumps(issue),flush=True)
raise SystemExit(bool(issues))
