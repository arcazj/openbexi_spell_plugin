"""Publish only the accepted master v0.6 and verify every downloaded asset."""
import argparse,gzip,hashlib,json,shutil,subprocess,tarfile,urllib.error,urllib.parse,urllib.request,uuid,zipfile
from pathlib import Path
from release_artifacts import stage_artifact, REASSEMBLE_SCRIPT
ROOT=Path(__file__).resolve().parents[1]
TAG='v0.6';API='https://api.github.com/repos/arcazj/openbexi_spell_plugin'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def tagged(commit,name):return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
def exact(row):
 p=Path(row['path']);assert sha(p)==row['sha256'],str(p);return p
parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);args=parser.parse_args()
commit=git('rev-parse',args.commit+'^{commit}')
assert git('ls-remote','origin','refs/heads/master').split()[0]==commit
assert git('rev-parse',TAG+'^{commit}')==commit
assert git('ls-remote','origin','refs/tags/'+TAG+'^{}').split()[0]==commit
manifest=json.loads(tagged(commit,'docs/V06_QUALIFICATION.json'))
assert manifest['v06_accepted'] is True and manifest['qualified']==763 and manifest['open']==0
assert manifest['release']=='v0.6' and manifest['stable_v1_accepted'] is False
OUT=ROOT/'.qualification/github-v06-release'/uuid.uuid4().hex;OUT.mkdir(parents=True)
print('Evidence: '+str(OUT),flush=True)
notes=tagged(commit,'docs/V06_RELEASE_NOTES.md')
release_body=notes.decode('utf-8').replace('(V06_QUALIFICATION.json)', '(https://github.com/arcazj/openbexi_spell_plugin/blob/v0.6/docs/V06_QUALIFICATION.json)')
assets=[];reassembled={}
for row in manifest['artifacts'].values():
 source=exact(row);staged,reassembly=stage_artifact(source,OUT)
 assets.extend(staged)
 if reassembly:
  assert reassembly['sha256']==row['sha256'] and reassembly['bytes']==source.stat().st_size
  reassembled[source.name]=reassembly
 else:assert sha(staged[0])==row['sha256']
if reassembled:
 helper=OUT/'reassemble_v06_evidence.py';helper.write_text(REASSEMBLE_SCRIPT,encoding='utf-8',newline='\n');assets.append(helper)
 if 'python reassemble_v06_evidence.py' not in release_body:release_body+='\n\nThe evidence archive is split into numbered parts. Download every `.partNNN` asset, `RELEASE_MANIFEST.json` and `reassemble_v06_evidence.py` into one folder, then run `python reassemble_v06_evidence.py`. The script verifies each part and the reconstructed archive against SHA-256 checksums.\n'
for name,body in [('V06_QUALIFICATION.json',tagged(commit,'docs/V06_QUALIFICATION.json')),('RELEASE_NOTES.md',notes),('V06_INSTALLATION.md',tagged(commit,'docs/V06_INSTALLATION.md'))]:
 p=OUT/name;p.write_bytes(body);assets.append(p)
prefix='openbexi_spell_plugin-v0.6/'
source_zip=OUT/'openbexi_spell_plugin-v0.6.zip'
subprocess.run(['git','archive','--format=zip','--prefix='+prefix,'--output='+str(source_zip),commit],cwd=ROOT,check=True)
source_tar=OUT/'openbexi_spell_plugin-v0.6.tar'
subprocess.run(['git','archive','--format=tar','--prefix='+prefix,'--output='+str(source_tar),commit],cwd=ROOT,check=True)
source_tgz=OUT/'openbexi_spell_plugin-v0.6.tar.gz'
with source_tar.open('rb') as inp,source_tgz.open('wb') as out:
 with gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0) as compressed:shutil.copyfileobj(inp,compressed)
with zipfile.ZipFile(source_zip) as archive:
 assert archive.testzip() is None
 assert archive.read(prefix+'README.md')==tagged(commit,'README.md')
 assert archive.read(prefix+'conformance/coverage.json')==tagged(commit,'conformance/coverage.json')
with tarfile.open(source_tgz,'r:gz') as archive:
 assert archive.extractfile(prefix+'conformance/coverage.json').read()==tagged(commit,'conformance/coverage.json')
assets.extend([source_zip,source_tgz])
release_manifest=OUT/'RELEASE_MANIFEST.json'
release_manifest.write_text(json.dumps(dict(tag=TAG,commit=commit,qualified=763,open=0,reassembled_artifacts=reassembled,assets={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in assets}),indent=2)+'\n',encoding='utf-8',newline='\n');assets.append(release_manifest)
checksums=OUT/'SHA256SUMS.txt';checksums.write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets),encoding='utf-8',newline='\n');assets.append(checksums)
assert len({p.name for p in assets})==len(assets)
assert all(p.stat().st_size<2*1024**3 for p in assets),'Split oversized assets before creating the GitHub release (2 GiB per-file limit)'
credential=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,check=True)
fields=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
headers={'Authorization':'Bearer '+fields['password'],'Accept':'application/vnd.github+json','User-Agent':'OpenBEXI-release','X-GitHub-Api-Version':'2022-11-28'}
def request(url,data=None,content_type='application/json',method=None):
 req=urllib.request.Request(url,data=data,headers={**headers,'Content-Type':content_type},method=method)
 with urllib.request.urlopen(req,timeout=120) as reply:return json.load(reply)

def upload(url,path):
 # Stream large qualification captures without loading the archive into RAM.
 with path.open('rb') as body:
  req=urllib.request.Request(url,data=body,headers={**headers,'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)},method='POST')
  with urllib.request.urlopen(req,timeout=120) as reply:return json.load(reply)
try:release=request(API+'/releases/tags/'+TAG)
except urllib.error.HTTPError as error:
 if error.code!=404:raise
 release=request(API+'/releases',json.dumps(dict(tag_name=TAG,target_commitish=commit,name='OpenBEXI SPELL v0.6 — Reproducible packages and installed hosts',draft=True,prerelease=False,body=release_body)).encode())
existing={a['name']:a for a in request(API+'/releases/'+str(release['id'])+'/assets?per_page=100')}
for path in assets:
 if path.name in existing:
  asset=existing[path.name]
  assert asset['size']==path.stat().st_size and asset.get('digest')=='sha256:'+sha(path), 'Existing asset differs: '+path.name
  continue
 print('Uploading '+path.name,flush=True)
 uploaded=upload(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(path.name),path)
 assert uploaded['size']==path.stat().st_size
# Draft asset downloads require the authenticated asset API. Public verification
# follows publication and additionally checks the public download URLs.
remote={a['name']:a for a in request(API+'/releases/'+str(release['id'])+'/assets?per_page=100')}
for path in assets:
 asset=remote[path.name];assert asset['size']==path.stat().st_size
 digest=asset.get('digest')
 if digest is not None:assert digest=='sha256:'+sha(path)
release=request(API+'/releases/'+str(release['id']),json.dumps(dict(draft=False,body=release_body)).encode(),method='PATCH')
remote={a['name']:a for a in request(API+'/releases/'+str(release['id'])+'/assets?per_page=100')}
verified=[]
part_owners={part:name for name,row in reassembled.items() for part in row['parts']}
whole={name:hashlib.sha256() for name in reassembled};sizes={name:0 for name in reassembled}
for path in assets:
 asset=remote[path.name]
 req=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'OpenBEXI-release'})
 digest=hashlib.sha256();size=0
 with urllib.request.urlopen(req,timeout=120) as source:
  for block in iter(lambda:source.read(4*1024*1024),b''):
   digest.update(block);size+=len(block)
   if path.name in part_owners:
    owner=part_owners[path.name];whole[owner].update(block);sizes[owner]+=len(block)
 assert size==path.stat().st_size and digest.hexdigest()==sha(path),path.name
 verified.append(dict(name=path.name,url=asset['browser_download_url'],sha256=digest.hexdigest(),bytes=size))
 print('Downloaded and verified '+path.name,flush=True)
reassembled_verified=[]
for name,row in reassembled.items():
 assert whole[name].hexdigest()==row['sha256'] and sizes[name]==row['bytes'],name
 reassembled_verified.append(dict(name=name,sha256=whole[name].hexdigest(),bytes=sizes[name],parts=row['parts']))
result=dict(passed=True,url=release['html_url'],tag=TAG,commit=commit,assets=verified,reassembled_artifacts_verified=reassembled_verified)
(OUT/'publication.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(passed=True,url=release['html_url'],commit=commit,assets=len(verified),evidence=str(OUT/'publication.json'))),flush=True)
