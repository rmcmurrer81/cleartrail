export class PythonBridge {
 constructor(workerURL,{onStage=()=>{},timeout=120000}={}){this.worker=new Worker(workerURL,{type:'module'});this.pending=new Map();this.nextId=1;this.timeout=timeout;this.worker.onmessage=({data})=>{if(data.event==='stage'){onStage(data.message);return;}const request=this.pending.get(data.id);if(!request)return;this.pending.delete(data.id);clearTimeout(request.timer);if(data.error)request.reject(Error(data.error));else request.resolve(data.result);};this.worker.onerror=event=>{for(const request of this.pending.values()){clearTimeout(request.timer);request.reject(Error(event.message||'The browser worker could not start.'));}this.pending.clear();};}
 request(operation,data={}){const id=this.nextId++;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('The browser operation took too long. Your last saved project remains available.'));},this.timeout);this.pending.set(id,{resolve,reject,timer});this.worker.postMessage({id,operation,...data});});}
 initialize(options){return this.request('initialize',{options});}
 call(payload){return this.request('call',{payload});}
 writeFile(path,bytes){return this.request('writeFile',{path,bytes});}
 readFile(path){return this.request('readFile',{path});}
 close(){this.worker.terminate();for(const request of this.pending.values()){clearTimeout(request.timer);request.reject(Error('The browser worker closed.'));}this.pending.clear();}
}
