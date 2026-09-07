"""Browser-only adapter for ClearTrail's exact evidence engine.

The MCP messages execute in this worker. This is a local protocol simulation,
not a remotely connected Alexa or HTTP MCP server. No provider is called.
"""
import base64,io,json,re,sqlite3,time,zipfile,shutil
from pathlib import Path
from evidence import EvidenceStore,TOOLS
from sarah_evidence import prepare,VERSION
from assistant_chat import help_reply,history,remember,summary

PROTOCOL='2025-11-25'
ROOT=Path('/workspace/cleartrail-state')
store=None
sessions={}
sequence=0

def get_store():
    global store
    if store is None:store=EvidenceStore(ROOT)
    return store

def rpc(payload,sid=''):
    global sequence
    if not isinstance(payload,dict) or payload.get('jsonrpc')!='2.0':raise ValueError('A JSON-RPC 2.0 object is required.')
    method=payload.get('method');rid=payload.get('id');params=payload.get('params') or {};changed=False
    if method=='initialize':
        if rid is None or params.get('protocolVersion')!=PROTOCOL:raise ValueError('Unsupported MCP initialization.')
        sequence+=1;sid='browser-session-'+str(sequence);sessions[sid]=False
        result={'protocolVersion':PROTOCOL,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'cleartrail-browser-simulation','version':'1.0.0'},'instructions':'Read original evidence. Labels and recency do not prove approval.'}
    else:
        if sid not in sessions:raise ValueError('Initialize a session first.')
        if method=='notifications/initialized':sessions[sid]=True;return {'status':202,'body':None,'session':sid,'changed':False}
        if not sessions[sid]:raise ValueError('Finish session initialization first.')
        if method=='ping':result={}
        elif method=='tools/list':result={'tools':[{'name':n,'description':d,'inputSchema':s,'annotations':{'readOnlyHint':r,'destructiveHint':False,'idempotentHint':r,'openWorldHint':False}} for n,d,s,r in TOOLS]}
        elif method=='tools/call':
            try:
                name=params.get('name');value=get_store().call(name,params.get('arguments',{}))
                changed=name in ('create_project','import_document','export_briefing')
                result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':False}
            except Exception as exc:result={'content':[{'type':'text','text':str(exc)[:1000]}],'isError':True}
        else:return {'status':200,'body':{'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}},'changed':False}
    return {'status':200,'body':{'jsonrpc':'2.0','id':rid,'result':result},'session':sid,'changed':changed}

class LocalProtocolClient:
    def __init__(self):
        self.seq=0;self.sid=''
        self.rpc('initialize',{'protocolVersion':PROTOCOL})
        self.rpc('notifications/initialized')
    def rpc(self,method,params=None):
        self.seq+=1;r=rpc({'jsonrpc':'2.0','id':self.seq,'method':method,'params':params or {}},self.sid);self.sid=r.get('session',self.sid)
        return (r.get('body') or {}).get('result',{})
    def call(self,name,arguments):
        result=self.rpc('tools/call',{'name':name,'arguments':arguments})
        if result.get('isError'):raise ValueError(result['content'][0]['text'])
        return result['structuredContent']
    def close(self):sessions.pop(self.sid,None)

def ask(payload):
    project_id=payload.get('project_id');question=payload.get('question')
    if payload.get('mode','sarah')!='sarah':raise ValueError('This browser edition uses Sarah without a local model.')
    if not isinstance(question,str) or not 1<=len(question.strip())<=2000:raise ValueError('Ask a question of 1 to 2,000 characters.')
    s=get_store();count=len(s.list_sources(project_id)['sources']) if project_id else 0
    q=question.casefold()
    if re.search(r'hear you|your voice|can you speak|talk out loud|no sound|play.*voice',q):reply='This browser edition uses written replies. No voice folder, installed model, key or credits are needed. Ask me about your records and I will keep the evidence beside the answer.'
    elif re.search(r'credits|api key|installed model',q):reply='Sarah conversation, evidence checks and exports work in this browser without a model, API key or credits. Your records are saved in this browser. Save a workspace copy to keep a backup.'
    else:reply=help_reply(question,count)
    if reply:return {'reply':reply,'conversation_entry':remember(s,project_id,question,reply)}
    if len(question.strip())<3:raise ValueError('Ask an evidence question of at least 3 characters.')
    client=LocalProtocolClient();trace=[]
    try:
        client.rpc('tools/list')
        context=client.call('get_context',{'project_id':project_id,'question':question})
        trace.append({'tool':'get_context','project_id':project_id,'source_count':len(context['sources']),'snapshot_sha256':context['snapshot_sha256'],'transport':'browser MCP simulation'})
        previous=client.call('list_briefings',{'project_id':project_id})['briefings'][:2]
        trace.append({'tool':'list_briefings','project_id':project_id,'count':len(previous),'transport':'browser MCP simulation'})
        started=time.monotonic();draft=prepare(context,question,previous,client,trace)
        value=s.save_briefing(project_id,context['snapshot_sha256'],question,draft,{'provider':'builtin_evidence','name':VERSION,'real_model_call':False,'elapsed_seconds':round(time.monotonic()-started,3)},trace)
        spoken=summary(value['briefing']);value['conversation_entry']=remember(s,project_id,question,spoken,value['briefing']['id']);value['spoken_reply']=spoken
        return value
    finally:client.close()

def snapshot():
    s=get_store();s.db.commit();out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('CLEARTRAIL-WORKSPACE.json',json.dumps({'schema':1,'app':'ClearTrail','protocol':PROTOCOL}))
        for p in sorted(ROOT.rglob('*')):
            if p.is_file():z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    raw=out.getvalue()
    if len(raw)>50*1024*1024:raise ValueError('This browser workspace has reached its 50 MB backup limit. Your last saved copy is preserved.')
    return base64.b64encode(raw).decode()

def restore(encoded):
    global store
    folder=Path('/workspace/cleartrail-restore')
    if folder.exists():shutil.rmtree(folder)
    folder.mkdir(parents=True)
    try:
        if encoded:
            raw=base64.b64decode(encoded,validate=True)
            if len(raw)>50*1024*1024:raise ValueError('Choose a ClearTrail workspace copy under 50 MB.')
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names=z.namelist()
                if len(names)!=len(set(names)) or len(names)>10000 or sum(i.file_size for i in z.infolist())>200*1024*1024:raise ValueError('Invalid or oversized workspace copy.')
                meta=json.loads(z.read('CLEARTRAIL-WORKSPACE.json'))
                if meta.get('schema')!=1 or meta.get('app')!='ClearTrail':raise ValueError('Choose a ClearTrail workspace copy.')
                for name in names:
                    if name=='CLEARTRAIL-WORKSPACE.json':continue
                    if not re.fullmatch(r'cleartrail\.sqlite3|attachments/[a-f0-9]{64}|exports/[a-zA-Z0-9_.-]+\.md',name):raise ValueError('Unexpected workspace file.')
                    target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
            db=sqlite3.connect(folder/'cleartrail.sqlite3')
            try:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('The saved database is damaged.')
                if db.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:raise ValueError('Unexpected active database content.')
                if {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}-{'projects','sources','briefings','conversations'}:raise ValueError('Unexpected database tables.')
            finally:db.close()
        if store is not None:store.close();store=None
        if ROOT.exists():shutil.rmtree(ROOT)
        folder.rename(ROOT);get_store()
        return {'projects':len(get_store().list_projects()['projects'])}
    finally:
        if folder.exists():shutil.rmtree(folder)

def dispatch(payload):
    try:
        if not isinstance(payload,dict):raise ValueError('Send an object.')
        operation=payload.get('operation')
        if operation=='snapshot':return {'snapshot':snapshot()}
        if operation=='restore':return restore(payload.get('snapshot'))
        if operation=='request':
            route=payload.get('path');body=payload.get('body') or {}
            if route=='/api/bootstrap':return {'status':200,'body':{'name':'ClearTrail','version':'2026.09.07-browser-1','token':'browser-only','protocol':PROTOCOL,'voice_available':False,'experience':'Browser MCP simulation; no Alexa device connected'},'changed':False}
            if route=='/mcp':return rpc(body,payload.get('session',''))
            if route=='/api/conversation':return {'status':200,'body':{'conversation':history(get_store(),body.get('project_id'))},'changed':False}
            if route=='/api/ask':return {'status':200,'body':ask(body),'changed':True}
            if route=='/api/speech':raise ValueError('Written replies are available in this browser edition.')
            return {'status':404,'body':{'error':'Not found'},'changed':False}
        raise ValueError('Unsupported browser operation.')
    except Exception as exc:
        if payload.get('operation')=='request':return {'status':400,'body':{'error':str(exc)[:1200]},'changed':False}
        raise
