/* IndexedDB commits resolve on transaction completion, including atomic snapshots + media. */
export class BrowserStore {
 constructor(name){if(!/^[a-z0-9_-]{3,80}$/i.test(name))throw Error('Invalid browser workspace name.');this.ready=new Promise((resolve,reject)=>{const request=indexedDB.open(name,1);request.onupgradeneeded=()=>request.result.createObjectStore('items');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);request.onblocked=()=>reject(Error('Close the older app tab to update browser storage.'));});}
 async get(key){const db=await this.ready;return new Promise((resolve,reject)=>{const request=db.transaction('items').objectStore('items').get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});}
 async keys(){const db=await this.ready;return new Promise((resolve,reject)=>{const request=db.transaction('items').objectStore('items').getAllKeys();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});}
 async put(key,value){return this.putMany([[key,value]]);}
 async putMany(entries){const db=await this.ready;return new Promise((resolve,reject)=>{const tx=db.transaction('items','readwrite');for(const [key,value] of entries)tx.objectStore('items').put(value,key);tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error||Error('Browser storage could not save this project. Export a backup before closing.'));tx.onerror=()=>reject(tx.error);});}
 async remove(key){const db=await this.ready;return new Promise((resolve,reject)=>{const tx=db.transaction('items','readwrite');tx.objectStore('items').delete(key);tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error);});}
 async close(){(await this.ready).close();}
}
