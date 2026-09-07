/* Generic isolated Python worker. It invokes one trusted adapter's dispatch(payload). */
let py=null,ready=false,queue=Promise.resolve();
const stage=message=>self.postMessage({event:'stage',message});
function localURL(input){const url=new URL(input,self.location.href);if(url.origin!==self.location.origin)throw Error('Browser runtime assets must come from this app origin.');return url.href;}
function workspacePath(input){if(typeof input!=='string'||!input.startsWith('/workspace/')||input.split('/').some(p=>p==='..'||p==='.')||input.includes('\\'))throw Error('Choose a workspace-relative file.');return input;}
async function initialize(options){
 if(ready)return{ready:true,python:py.runPython('import sys; sys.version.split()[0]')};
 const base=new URL(localURL(options.runtimeURL||'./pyodide/'));if(!base.pathname.endsWith('/'))base.pathname+='/';
 stage('Preparing the free planning engine…');
 const {loadPyodide}=await import(new URL('pyodide.mjs',base).href);
 py=await loadPyodide({indexURL:base.href,stdout:()=>{},stderr:()=>{}});
 py.FS.mkdirTree('/app');py.FS.mkdirTree('/workspace');
 for(const file of options.files||[]){if(!/^[A-Za-z0-9_.\/-]+$/.test(file.path)||file.path.split('/').includes('..')||file.path.startsWith('/'))throw Error('Invalid adapter asset path.');const response=await fetch(localURL(file.url));if(!response.ok)throw Error('An application file could not load: '+file.path);const bytes=new Uint8Array(await response.arrayBuffer());if(file.sha256){const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');if(hash!==file.sha256)throw Error('An application file did not match its manifest.');}const target='/app/'+file.path;py.FS.mkdirTree(target.slice(0,target.lastIndexOf('/')));py.FS.writeFile(target,bytes);}
 if(options.packages?.length){stage('Preparing document support…');await py.loadPackage(options.packages);}
 const entrypoint=options.entrypoint||'browser_adapter';if(!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(entrypoint))throw Error('Invalid browser adapter.');
 py.globals.set('__adapter_name',entrypoint);py.globals.set('__extra_paths',JSON.stringify(options.extraPaths||[]));
 await py.runPythonAsync("import sys,json,importlib\nsys.path.insert(0,'/app')\nfor p in json.loads(__extra_paths):\n if not p.startswith('/app/') or '..' in p.split('/'): raise ValueError('Invalid Python asset path')\n sys.path.insert(0,p)\n__browser_adapter=importlib.import_module(__adapter_name)\n");
 ready=true;stage('Free planning is ready.');return{ready:true,python:py.runPython('sys.version.split()[0]')};
}
async function execute(message){
 if(message.operation==='initialize')return initialize(message.options||{});
 if(!ready)throw Error('The free browser engine is still preparing.');
 if(message.operation==='call'){py.globals.set('__payload_json',JSON.stringify(message.payload));const result=await py.runPythonAsync('json.dumps(__browser_adapter.dispatch(json.loads(__payload_json)),ensure_ascii=False,allow_nan=False)');return JSON.parse(result);}
 if(message.operation==='writeFile'){const target=workspacePath(message.path);py.FS.mkdirTree(target.slice(0,target.lastIndexOf('/')));py.FS.writeFile(target,new Uint8Array(message.bytes));return{bytes:message.bytes.byteLength};}
 if(message.operation==='readFile'){return py.FS.readFile(workspacePath(message.path));}
 throw Error('Unsupported browser operation.');
}
self.onmessage=event=>{const message=event.data;queue=queue.then(async()=>{try{self.postMessage({id:message.id,result:await execute(message)});}catch(error){self.postMessage({id:message.id,error:error.message||String(error)});}});};
