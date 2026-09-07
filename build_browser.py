"""Build static browser assets from pinned sources. Run with Python 3.10+; no pip required."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,urllib.request,zipfile
ROOT=Path(__file__).resolve().parent
sha=lambda data:hashlib.sha256(data).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/browser');parser.add_argument('--cache',type=Path,default=ROOT/'.build-cache');args=parser.parse_args()
 output=args.output.resolve();cache=args.cache.resolve()
 if output.exists():raise SystemExit('Choose a new output directory; existing files will not be overwritten.')
 spec=json.loads((ROOT/'browser-dependencies.json').read_text(encoding='utf-8'));cache.mkdir(parents=True,exist_ok=True)
 shutil.copytree(ROOT/'browser',output);downloads=[]
 for dependency in spec['dependencies']:
  cached=cache/dependency['sha256']
  if cached.exists():data=cached.read_bytes()
  else:
   request=urllib.request.Request(dependency['url'],headers={'User-Agent':'HackathonSourceBuild/1'})
   with urllib.request.urlopen(request,timeout=90) as response:data=response.read(40000000)
   if sha(data)!=dependency['sha256']:raise ValueError('Upstream download hash mismatch: '+dependency['url'])
   cached.write_bytes(data)
  if sha(data)!=dependency['sha256']:raise ValueError('Cached dependency hash mismatch')
  target=output/dependency['path'];target.parent.mkdir(parents=True,exist_ok=True)
  if dependency.get('kind')=='pypdf-source-zip':
   memory=io.BytesIO()
   with zipfile.ZipFile(io.BytesIO(data)) as wheel,zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for member in dependency['members']:
     content=wheel.read(member['wheel_path'])
     if sha(content)!=member['sha256']:raise ValueError('pypdf source content hash mismatch: '+member['path'])
     info=zipfile.ZipInfo(member['path'],(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
     archive.writestr(info,content,compresslevel=9)
   target.write_bytes(memory.getvalue())
   files_path=output/'browser-files.json';files=json.loads(files_path.read_text(encoding='utf-8'))
   for item in files['files']:
    if item['path']==dependency['path']:item['sha256']=sha(target.read_bytes())
   files_path.write_text(json.dumps(files,indent=2)+'\n',encoding='utf-8')
  else:target.write_bytes(data)
  downloads.append({'path':dependency['path'],'upstream_sha256':dependency['sha256'],'output_sha256':sha(target.read_bytes())})
 generated=[{'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(output.rglob('*')) if p.is_file()]
 expected={x['path']:x['sha256'] for x in spec['verified_release_files']};actual={x['path']:x['sha256'] for x in generated}
 allowed={'vendor/pypdf.zip','browser-files.json'} if any(d.get('kind')=='pypdf-source-zip' for d in spec['dependencies']) else set()
 differences=[p for p in expected if expected[p]!=actual.get(p)]
 if set(differences)-allowed:raise ValueError('Unexpected difference from verified application assets: '+repr(differences))
 if set(actual)!=set(expected):raise ValueError('Unexpected missing or added build files')
 receipt={'entrypoint':'index.html','files':generated,'downloads':downloads,'verified_release_differences':differences,'pypdf_source_content_verified':bool(allowed),'note':'Archive compression and browser-files.json hash may differ; every pypdf source byte is verified. All other application/runtime bytes match the verified release.'}
 (output.parent/(output.name+'-build-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'output':str(output),'files':len(generated),'bytes':sum(x['bytes'] for x in generated),'release_differences':differences}))
if __name__=='__main__':main()
