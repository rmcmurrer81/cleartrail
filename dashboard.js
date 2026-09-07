function svgNode(tag, attrs={}){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));return node}
function drawSourceChart(){
 const host=$('sourceChart');host.replaceChildren();
 if(!sources.length){host.append(el('div','Add a document or save a note. The chart will show the records you actually have.','chart-empty'));return}
 const kinds=[['notes','Notes'],['proposal','Proposals'],['decision','Decision records']];
 const chart=svgNode('svg',{viewBox:'0 0 540 176',role:'img','aria-label':'Saved sources grouped by the labels you selected'});
 kinds.forEach(([kind,label],i)=>{const count=sources.filter(s=>s.kind===kind).length;const y=20+i*53;
  const text=svgNode('text',{x:0,y:y+17,class:'chart-label'});text.textContent=label;chart.append(text);
  chart.append(svgNode('rect',{x:155,y,width:335,height:26,rx:7,class:'bar-track'}));
  if(count)chart.append(svgNode('rect',{x:155,y,width:335*count/sources.length,height:26,rx:7,class:'bar-'+kind}));
  const value=svgNode('text',{x:507,y:y+18,class:'chart-value'});value.textContent=count;chart.append(value);
 });host.append(chart);
}
function renderDashboard(){
 if(!$('sourceChart'))return;
 drawSourceChart();
 const latest=activeBriefing||briefings[0];
 $('issueCount').textContent=latest?latest.conflicts.length:'—';
 $('issueHint').textContent=latest?'In the selected saved review':'Ask Sarah to review your sources';
 $('dashboardProject').textContent=$('project').selectedOptions[0]?.textContent||'Your workspace';
 const focus=$('attentionList');focus.replaceChildren();
 if(!latest){focus.append(el('div',sources.length?'Your sources are saved. Ask “What changed?” to check their wording.':'Start with a question, a note, or a document. Sarah can help you choose the next step.','chart-empty'))}
 else if(latest.conflicts.length){latest.conflicts.forEach(c=>{const card=el('article',undefined,'attention-card');card.append(el('strong','Different decisions to review'),el('p',c.text));c.citations.forEach(q=>{const b=el('button',q.title+' · '+q.revision,'quiet');b.onclick=()=>openEvidence(q.source_id,q.quote);card.append(b)});focus.append(card)})}
 else{focus.append(el('div',latest.answer_kind==='abstention'?'No matching evidence was found for that question. Add the missing source or try a different question.':'No conflicting decision wording was flagged in this review. That does not establish approval.','chart-empty'))}
 const trail=$('revisionTrail');trail.replaceChildren();
 const groups=new Map();for(const source of sources){const list=groups.get(source.document_key)||[];list.push(source);groups.set(source.document_key,list)}
 if(!groups.size){trail.append(el('div','Each saved version will appear here. Open a version to see its exact words.','chart-empty'));return}
 for(const [name,list] of groups){const group=el('div',undefined,'revision-group');group.append(el('h3',name));const chain=el('div',undefined,'revision-chain');
  // Follow the recorded parent links. Uploaded date alone never establishes authority.
  const byId=new Map(list.map(s=>[s.id,s]));const visited=new Set();const ordered=[];
  function visit(s){if(visited.has(s.id))return;visited.add(s.id);if(byId.has(s.parent_source_id))visit(byId.get(s.parent_source_id));ordered.push(s)}
  list.forEach(visit);
  for(const source of ordered){const card=el('button',undefined,'revision-node '+source.kind);card.append(el('span',source.kind==='decision'?'Decision record':source.kind==='proposal'?'Proposal':'Note','node-kind'),el('strong',source.revision),el('small',source.title));if(source.parent_source_id)card.append(el('span','↳ linked to earlier version','node-link'));card.onclick=()=>openEvidence(source.id);chain.append(card)}
  group.append(chain);trail.append(group);
 }
}
document.querySelectorAll('[data-focus]').forEach(button=>button.onclick=()=>{
 document.querySelectorAll('[data-focus]').forEach(b=>b.classList.toggle('active',b===button));
 const target=$(button.dataset.focus);target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
});
document.querySelectorAll('[data-question]').forEach(button=>button.onclick=()=>{$('question').value=button.dataset.question;$('ask').click()});
