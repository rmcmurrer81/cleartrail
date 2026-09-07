import {PythonBridge} from './runtime/python-rpc.mjs';
import {BrowserStore} from './runtime/browser-store.mjs';
const byId=id=>document.getElementById(id),loading=byId('browserLoading'),stage=byId('browserStage');
let db;
const bridge=new PythonBridge(new URL('./runtime/python-rpc-worker.mjs',import.meta.url),{onStage:message=>stage.textContent=message});
let revision=null,localQueue=Promise.resolve();
const lock=fn=>{const action=()=>navigator.locks.request('cleartrail-browser-workspace-v1',fn);const r=localQueue.then(action,action);localQueue=r.catch(()=>{});return r};
async function sync(){const saved=await db.get('workspace');if(saved?.revision!==revision){await bridge.call({operation:'restore',snapshot:saved?.snapshot||null});revision=saved?.revision||null;}return saved;}
async function request(path,options={}){
 return lock(async()=>{const saved=await sync();const headers=new Headers(options.headers||{});let body=options.body?JSON.parse(options.body):{};const result=await bridge.call({operation:'request',path,body,session:headers.get('MCP-Session-Id')||''});
  const failed=result.status>=400||result.body?.result?.isError;
  if(failed)await bridge.call({operation:'restore',snapshot:saved?.snapshot||null});
  if(result.changed){try{const next=await bridge.call({operation:'snapshot'}),id=crypto.randomUUID();await db.put('workspace',{schema:1,revision:id,snapshot:next.snapshot,saved_at:new Date().toISOString()});revision=id;}catch(error){await bridge.call({operation:'restore',snapshot:saved?.snapshot||null});throw Error('Your change could not be saved. Your previous workspace is intact. '+error.message);}}
  return new Response(result.body===null?null:JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json','MCP-Session-Id':result.session||headers.get('MCP-Session-Id')||''}});
 });
}
function download(name,bytes,mime='application/zip'){const u=URL.createObjectURL(new Blob([bytes],{type:mime})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),30000);}
function bytesFromBase64(value){const s=atob(value),out=new Uint8Array(s.length);for(let i=0;i<s.length;i++)out[i]=s.charCodeAt(i);return out;}
function base64FromBytes(bytes){let value='';for(let i=0;i<bytes.length;i+=16384)value+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(value);}
function addWorkspaceFiles(){
 const button=document.createElement('button');button.type='button';button.textContent='⋯';button.className='quiet workspace-file-button';button.setAttribute('aria-label','Workspace files and browser information');document.querySelector('.projectbar').append(button);
 const dialog=document.createElement('dialog');dialog.id='browserFilesDialog';dialog.innerHTML='<h2>Your workspace copies</h2><p>Your sources and conversations are saved in this browser. Keep a copy to move them to another computer or recover them if browser data is cleared.</p><button id="saveWorkspaceCopy">Save a workspace copy</button><label for="openWorkspaceCopy">Open a saved workspace copy</label><input id="openWorkspaceCopy" type="file" accept=".zip"><div id="copyReview" hidden><p>Opening a copy replaces the workspace in this browser. Save your current copy first if you want to keep it.</p><button id="confirmWorkspaceCopy">Open this copy</button></div><p id="browserFileStatus" role="status"></p><small>Written Sarah replies need no model, key or voice folder. The evidence tools run here as an MCP protocol simulation; no Alexa device is connected. <a href="./licenses/NOTICE.txt" target="_blank" rel="noopener">Source and license notices</a></small><button id="closeWorkspaceFiles" class="quiet">Back to workspace</button>';document.body.append(dialog);
 button.onclick=()=>dialog.showModal();byId('closeWorkspaceFiles').onclick=()=>dialog.close();
 byId('saveWorkspaceCopy').onclick=async()=>{try{byId('browserFileStatus').textContent='Preparing your copy…';await lock(async()=>{await sync();const {snapshot}=await bridge.call({operation:'snapshot'});download('ClearTrail-workspace-'+new Date().toISOString().slice(0,10)+'.zip',bytesFromBase64(snapshot));});byId('browserFileStatus').textContent='Your workspace copy was prepared for download.';}catch(e){byId('browserFileStatus').textContent=e.message;}};
 byId('openWorkspaceCopy').onchange=()=>{const file=byId('openWorkspaceCopy').files[0];byId('copyReview').hidden=!file;byId('browserFileStatus').textContent=file?'Selected: '+file.name:'';};
 byId('confirmWorkspaceCopy').onclick=async()=>{const file=byId('openWorkspaceCopy').files[0];if(!file)return;byId('confirmWorkspaceCopy').disabled=true;try{if(file.size>50*1024*1024)throw Error('Choose a workspace copy smaller than 50 MB.');const encoded=base64FromBytes(new Uint8Array(await file.arrayBuffer()));await lock(async()=>{const previous=await sync();try{await bridge.call({operation:'restore',snapshot:encoded});const snapshot=(await bridge.call({operation:'snapshot'})).snapshot;const id=crypto.randomUUID();await db.put('workspace',{schema:1,revision:id,snapshot,saved_at:new Date().toISOString()});revision=id;}catch(error){await bridge.call({operation:'restore',snapshot:previous?.snapshot||null});throw error;}});location.reload();}catch(error){byId('browserFileStatus').textContent='Copy could not be opened: '+error.message;}finally{byId('confirmWorkspaceCopy').disabled=false;}};
}
async function script(name){await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=new URL(name,import.meta.url);s.onload=resolve;s.onerror=()=>reject(Error('Could not open '+name));document.body.append(s);});}
try{
 if(!navigator.locks||!globalThis.indexedDB)throw Error('Use a current browser with local storage enabled to save this workspace.');
 db=new BrowserStore('cleartrail-browser-workspace-v1');await db.ready;
 const manifest=await(await fetch(new URL('browser-files.json',import.meta.url))).json();
 await bridge.initialize({runtimeURL:new URL('./runtime/pyodide/',import.meta.url).href,entrypoint:'browser_adapter',files:manifest.files.map(f=>({...f,url:new URL(f.url,import.meta.url).href})),extraPaths:['/app/vendor/pypdf.zip']});
 await lock(()=>sync());window.clearTrailBackend={fetch:request};
 for(const name of ['app.js','dashboard.js','voice-ui.js','fixed-workspace.js','responsive-navigation.js'])await script(name);
 await window.clearTrailStart();
 document.querySelectorAll('#mode option').forEach(o=>{if(o.value!=='sarah')o.remove()});byId('mode').value='sarah';document.querySelector('.advanced-assistant').hidden=true;
 window.queueSarahReply=()=>{byId('voiceReplay').hidden=true;byId('voicePause').hidden=true;};byId('voiceToggle').hidden=true;byId('voiceReplay').hidden=true;byId('voiceState').textContent='Written replies · no setup or credits';
 document.querySelector('header>small').innerHTML='YOUR RECORDS · SAVED IN THIS BROWSER<br>Free conversation and evidence review';
 addWorkspaceFiles();loading.remove();
 import("./webmcp.mjs").catch(()=>{});
}catch(error){stage.textContent='The workspace could not open: '+error.message;byId('browserRetry').hidden=false;byId('browserRetry').onclick=()=>location.reload();}
