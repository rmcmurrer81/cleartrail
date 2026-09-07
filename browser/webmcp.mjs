const context=document.modelContext;
if(context?.registerTool){
 const lifecycle=new AbortController();
 const validate=(input,fields=[])=>{if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!fields.includes(k)))throw Error('Use the declared input fields.');};
 const ready=()=>{if(document.getElementById('browserLoading')||window.clearTrailBusy)throw Error('Wait for ClearTrail to finish the current action.');};
 const tools=[{
  name:'read_cleartrail_workspace',title:'Read current ClearTrail workspace',
  description:'Read the selected project and counts shown in the current evidence workspace. Does not return document contents.',
  inputSchema:{type:'object',properties:{},additionalProperties:false},
  annotations:{readOnlyHint:true,untrustedContentHint:true},
  execute(input){validate(input);ready();return {project:document.getElementById('project').selectedOptions[0]?.textContent||'',sources:Number(document.getElementById('sourceCount').textContent),revisions:Number(document.getElementById('revisionCount').textContent),reviews:Number(document.getElementById('reviewCount').textContent)};}
 },{
  name:'search_cleartrail_sources',title:'Search exact saved evidence',
  description:'Search the selected project’s saved source text, open the Sources screen and show exact matching lines. This does not decide which source is authoritative or alter source documents.',
  inputSchema:{type:'object',properties:{query:{type:'string',minLength:1,maxLength:400}},required:['query'],additionalProperties:false},
  annotations:{readOnlyHint:false,untrustedContentHint:true},
  async execute(input){validate(input,['query']);if(typeof input.query!=='string'||!input.query.trim()||input.query.length>400)throw Error('Enter a search phrase from 1 to 400 characters.');ready();if(Number(document.getElementById('sourceCount').textContent)<1)throw Error('Add a source to this project before searching.');window.chooseView('sources');document.getElementById('query').value=input.query;await document.getElementById('search').onclick();return {status:document.getElementById('status').textContent,matches:[...document.querySelectorAll('#matches .citation')].slice(0,20).map(e=>e.textContent)};}
 }];
 for(const tool of tools){try{Promise.resolve(context.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{}}
 window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
}
