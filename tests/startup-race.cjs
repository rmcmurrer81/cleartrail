const {chromium}=require(process.env.CLEARTRAIL_PLAYWRIGHT || 'playwright');
const http=require('node:http'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=__dirname,site=path.resolve(process.env.CLEARTRAIL_SITE_ROOT || path.join(root,'../browser'));
const candidate=path.resolve(process.env.CLEARTRAIL_CANDIDATE_DIR || site);
const cases=[
 {id:'original-empty-dashboard',candidate:false,delay:'dashboard.js',expected:'renderDashboard is not defined'},
 {id:'candidate-empty-dashboard',candidate:true,delay:'dashboard.js'},
 {id:'candidate-saved-dashboard',candidate:true,delay:'dashboard.js'},
 {id:'candidate-saved-fixed',candidate:true,delay:'fixed-workspace.js'},
 {id:'candidate-empty-responsive',candidate:true,delay:'responsive-navigation.js'},
 {id:'candidate-empty-script-retry',candidate:true,delay:'dashboard.js',failOnce:true},
];
const stubStore=`export class BrowserStore {ready=Promise.resolve();async get(){return null}async put(){window.__writes=(window.__writes||0)+1;}}`;
const stubBridge=`export class PythonBridge {
 async initialize(){window.__requests=[];window.__writes=0;}
 async call(v){if(v.operation==='restore')return {};if(v.operation==='snapshot')return {snapshot:'QA snapshot'};
  window.__requests.push({path:v.path,method:v.body?.method,name:v.body?.params?.name});
  if(v.path==='/api/bootstrap')return {status:200,body:{token:'isolated-test-fixture-token'}};
  if(v.path==='/api/conversation')return {status:200,body:{conversation:[]}};
  if(v.path==='/mcp'){
   if(v.body.method==='notifications/initialized')return {status:202,body:null};
   let result={};const saved=location.pathname.includes('saved');
   if(v.body.method==='tools/call'){
    const name=v.body.params.name;let content;
    if(name==='list_projects')content={projects:saved?[{id:'qa-project',name:'Saved QA project'}]:[]};
    else if(name==='list_sources')content={sources:[{id:'qa-source',title:'QA source',kind:'notes',document_key:'QA record',revision:'v1',text:'Saved fixture evidence.'}]};
    else if(name==='list_briefings')content={briefings:[]};
    else throw Error('Unexpected startup mutation or tool: '+name);
    result={structuredContent:content};
   }
   return {status:200,body:{result},session:'isolated-test-session'};
  }
  throw Error('Unexpected startup route '+v.path);
 }
}`;
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json'};
const server=http.createServer(async(req,res)=>{
 try{
  const parts=new URL(req.url,'http://localhost').pathname.split('/').filter(Boolean),caseId=parts.shift(),cfg=cases.find(c=>c.id===caseId);
  if(!cfg){res.writeHead(404).end();return;}const name=parts.join('/')||'index.html';
  if(name===cfg.delay){cfg.requests=(cfg.requests||0)+1;await new Promise(r=>setTimeout(r,900));if(cfg.failOnce&&cfg.requests===1){res.writeHead(503).end('Intentional test dependency failure');return;}}
  let content;
  if(name==='runtime/browser-store.mjs')content=stubStore;
  else if(name==='runtime/python-rpc.mjs')content=stubBridge;
  else if(name==='browser-files.json')content=JSON.stringify({files:[]});
  else {const folder=['app.js','browser-entry.mjs'].includes(name)?candidate:site;const file=path.resolve(folder,name);if(!file.startsWith(folder+path.sep))throw Error('outside fixture');content=await fs.readFile(file);
   if(!cfg.candidate&&name==='app.js'){const text=content.toString(),line=text.split('\n').find(v=>v.startsWith('window.clearTrailStart=async()=>{'));assert(line,'Expected fixed explicit startup');const restored=line.replace('window.clearTrailStart=async()=>{','(async()=>{').slice(0,-2)+'})();';content=text.replace(line,restored);}
   if(!cfg.candidate&&name==='browser-entry.mjs'){const text=content.toString();assert(text.includes(' await window.clearTrailStart();'));content=text.replace(' await window.clearTrailStart();\n','');}
  }
  res.writeHead(200,{'Content-Type':mime[path.extname(name)]||'application/octet-stream','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"});res.end(content);
 }catch(e){console.error('Fixture server:',req.url,String(e));res.writeHead(404).end(String(e));}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({channel:'msedge',headless:true});const receipt={scope:'Actual unmodified UI/loader scripts, candidate two-file overrides, strict no-eval CSP, deliberately delayed HTTP dependencies; backend is a deterministic read-only fixture, not live Pyodide acceptance.',cases:[]};
 try{
  for(const cfg of cases){const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[],responses=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.url().startsWith(origin))responses.push({file:new URL(r.url()).pathname,status:r.status()});});
   await page.goto(`${origin}/${cfg.id}/`,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>typeof window.clearTrailBackend==='object'&&[...document.scripts].some(s=>s.src.endsWith('/app.js')));
   await page.waitForTimeout(100);
   const before=await page.evaluate(()=>({loading:!!document.getElementById('browserLoading'),requests:window.__requests.slice(),writes:window.__writes,newDialogOpen:document.getElementById('newDialog').open}));
   if(cfg.candidate){assert.equal(before.requests.length,0,'Candidate must not begin bootstrap before all support scripts load');assert.equal(before.writes,0);}
   let earlyClickBlocked=false;try{await page.locator('#newProject').click({timeout:150});}catch{earlyClickBlocked=true;}
   assert(earlyClickBlocked,'Visible loading overlay must block normal project-creation click');
   if(cfg.failOnce){await page.waitForFunction(()=>!document.getElementById('browserRetry').hidden);const failed=await page.evaluate(()=>({stage:document.getElementById('browserStage').textContent,requests:window.__requests.slice(),writes:window.__writes,loading:!!document.getElementById('browserLoading')}));assert.match(failed.stage,/Could not open dashboard.js/);assert.equal(failed.requests.length,0);assert.equal(failed.writes,0);cfg.failureObservation=failed;await page.locator('#browserRetry').click();}
   await page.waitForFunction(()=>!document.getElementById('browserLoading'));
   const after=await page.evaluate(()=>({status:document.getElementById('status').textContent,renderDashboard:typeof window.renderDashboard,updatePath:typeof window.updatePath,requests:window.__requests.slice(),writes:window.__writes,sources:document.getElementById('sourceCount').textContent,conversation:document.getElementById('conversation').textContent}));
   if(cfg.expected)assert.equal(after.status,cfg.expected);else{assert.match(after.status,/Sarah is ready/);assert.match(after.conversation,/Sarah/);assert.equal(after.sources,cfg.id.includes('saved')?'1':'0');}
   assert.deepEqual(errors,[]);assert.equal(after.writes,0);
   receipt.cases.push({id:cfg.id,before,earlyClickBlocked,after,errors,responses,failureObservation:cfg.failureObservation||null,passed:true});await context.close();
  }
  receipt.passed=true;await fs.writeFile(path.resolve(process.env.CLEARTRAIL_REGRESSION_RECEIPT || path.join(root,'startup-race-result.json')),JSON.stringify(receipt,null,2));console.log(JSON.stringify({passed:true,cases:receipt.cases.map(c=>({id:c.id,status:c.after.status,requestsBeforeDependencies:c.before.requests.length,errors:c.errors}))},null,2));
 }catch(error){receipt.passed=false;receipt.error=String(error.stack||error);await fs.writeFile(path.resolve(process.env.CLEARTRAIL_REGRESSION_RECEIPT || path.join(root,'startup-race-result.json')),JSON.stringify(receipt,null,2));throw error;}
 finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
