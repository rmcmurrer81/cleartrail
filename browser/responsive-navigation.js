(function(){
 const nav=el('nav',undefined,'compact-navigation');nav.id='compactNavigation';nav.setAttribute('aria-label','Workspace screens');
 for(const [view,label,icon] of [['dashboard','Overview','▦'],['sources','Sources','▤'],['history','Versions','↗'],['review','Review','◎'],['chat','Sarah','◉']]){const b=el('button',undefined,'quiet');b.dataset.screen=view;b.append(el('span',icon),el('strong',label));b.onclick=()=>chooseView(view);nav.append(b)}document.body.append(nav);
 const baseChoose=chooseView;chooseView=function(view){baseChoose(view==='chat'?'dashboard':view);document.body.dataset.focusedScreen=view;ctView=view;nav.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.screen===view))};chooseView('dashboard');
 const add=el('button','Add a source','compact-add-source');add.onclick=()=>sourceForm();document.querySelector('.directory-screen').insertBefore(add,$('sourceDirectory'));
 const newReview=el('button','Open the saved review →','quiet open-review');newReview.onclick=()=>chooseView('review');document.querySelectorAll('.visual-card')[1].append(newReview);
 const originalPage=renderReviewPage;renderReviewPage=function(){originalPage();if(activeBriefing?.source_snapshot_outdated)$('answer').prepend(el('div','Sources have changed. Ask Sarah again for a fresh review.','stale-review'))};
 const beforeDirectory=renderSourceDirectory;renderSourceDirectory=function(){beforeDirectory();if(innerWidth<600){const cards=[...$('sourceDirectory').children];for(const card of cards.slice(2))card.hidden=true}};
})();

let ctDirectoryPage=0,ctMessagePages=[],ctHistoryPage=0;
function ctSplitText(text,limit){const chunks=[];let value=String(text);while(value.length>limit){let cut=value.lastIndexOf(' ',limit);if(cut<limit*.5)cut=limit;chunks.push(value.slice(0,cut));value=value.slice(cut).trimStart()}if(value)chunks.push(value);return chunks}
restoreConversation=async function(){const d=await(await localPost('/api/conversation',{project_id:current||null})).json();ctChatEntries=d.conversation;ctMessagePages=[];const limit=innerHeight<670?190:innerWidth<600?340:600;for(const e of ctChatEntries)for(const [role,text] of [['owner',e.question],['sarah',e.reply]])for(const chunk of ctSplitText(text,limit))ctMessagePages.push({role,text:chunk});ctChatPage=Math.max(0,ctMessagePages.length-1);renderChatPage()};
renderChatPage=function(){const box=$('conversation');box.replaceChildren();const item=ctMessagePages[ctChatPage];if(item){const card=el('div',undefined,'chat-message '+item.role);card.append(el('strong',item.role==='owner'?'You':'Sarah','chat-speaker'),el('div',item.text));box.append(card)}else box.append(el('div',"Hi, I'm Sarah. Choose Help me start, or tell me what you're working on.",'chat-message sarah'));setPager('chatPager',ctChatPage,ctMessagePages.length)};
renderSourceDirectory=function(){const host=$('sourceDirectory');if(!host)return;host.replaceChildren();const size=innerWidth<600?(innerHeight<670?1:2):innerHeight<850?2:4;const pages=Math.ceil(sources.length/size);ctDirectoryPage=Math.min(ctDirectoryPage,Math.max(0,pages-1));for(const source of sources.slice(ctDirectoryPage*size,(ctDirectoryPage+1)*size)){const card=el('button',undefined,'directory-card');card.append(el('span',source.kind,'node-kind'),el('strong',source.title),el('span',source.document_key+' · '+source.revision),el('small','Open exact source →'));card.onclick=()=>openEvidence(source.id);host.append(card)}if(!sources.length)host.append(el('div','Add a source, or save your words from the conversation.','chart-empty'));setPager('directoryPager',ctDirectoryPage,pages)};
$('directoryPager').children[0].onclick=()=>{ctDirectoryPage--;renderSourceDirectory()};$('directoryPager').children[2].onclick=()=>{ctDirectoryPage++;renderSourceDirectory()};
const ctPreviousDashboard=renderDashboard;
renderDashboard=function(){ctPreviousDashboard();const host=$('attentionList'),review=activeBriefing||briefings[0];host.replaceChildren();const count=review?.conflicts?.length||0;if(count){const card=el('div',undefined,'attention-compact');card.append(el('strong',count+' possible '+(count===1?'disagreement':'disagreements')),el('p','Decision records contain different wording. Compare the quoted passages in the review.'));host.append(card)}else host.append(el('div',review?'No conflicting decision wording was flagged in this review.':'Ask Sarah what changed to check your saved records.','chart-empty'));renderSourceDirectory();ctPageHistory()};
function ctPageHistory(){const group=[...$('revisionTrail').children].find(e=>!e.hidden);if(!group)return;const chain=group.querySelector('.revision-chain');if(!chain)return;const nodes=[...chain.children];const size=innerWidth<600?2:innerHeight<850?4:6;const pages=Math.ceil(nodes.length/size);ctHistoryPage=Math.min(ctHistoryPage,Math.max(0,pages-1));nodes.forEach((e,i)=>e.hidden=Math.floor(i/size)!==ctHistoryPage);setPager('historyRevisionPager',ctHistoryPage,pages)}
document.querySelector('.trail-panel').append(pageControls('historyRevisionPager',()=>{ctHistoryPage--;ctPageHistory()},()=>{ctHistoryPage++;ctPageHistory()}));
$('historyGroup').onchange=()=>{ctHistoryPage=0;renderHistorySelection();ctPageHistory()};
const ctWholeReviewParts=reviewParts;
reviewParts=function(b){if(innerWidth>=600&&innerHeight>=820)return ctWholeReviewParts(b);const result=[];for(const item of ctWholeReviewParts(b)){if(item.type==='finding'||item.type==='conflict'){for(const chunk of ctSplitText(item.value.text,innerHeight<670?220:400))result.push({type:'small-intro',value:{text:chunk,label:item.type==='conflict'?'Different decisions to review':'Matching evidence'}});for(const c of item.value.citations)for(const chunk of ctSplitText(c.quote,innerHeight<670?200:360))result.push({type:'small-quote',value:{...c,preview:chunk}})}else if(item.type==='unknown'){for(const chunk of ctSplitText(item.value,220))result.push({type:'small-intro',value:{text:chunk,label:'Still unknown'}})}else result.push(item)}return result};
const ctRenderLargeReview=renderReviewPage;
renderReviewPage=function(){if(innerWidth>=600&&innerHeight>=820){ctRenderLargeReview();return}const host=$('answer'),b=activeBriefing;host.replaceChildren();if(!b){host.append(el('div','Ask Sarah to review your sources.','chart-empty'));return}const parts=reviewParts(b);ctReviewPage=Math.min(ctReviewPage,Math.max(0,parts.length-1));const item=parts[ctReviewPage];if(item){const box=el('div',undefined,'review-part');if(item.type==='small-intro')box.append(el('h3',item.value.label),el('p',item.value.text));else if(item.type==='small-quote'){box.append(el('h3',item.value.title),el('p',item.value.preview));const button=el('button','Read source · '+item.value.revision,'quiet source-detail-button');button.onclick=()=>openEvidence(item.value.source_id,item.value.quote);box.append(button)}else if(item.type==='comparison'){box.append(el('h3','Exact revision comparison'));const button=el('button','Open comparison','quiet');button.onclick=()=>openPagedText(item.value.document_key,item.value.diff);box.append(button)}host.append(box)}setPager('reviewPager',ctReviewPage,parts.length)};
addEventListener('resize',()=>{ctChatPage=0;restoreConversation();renderDashboard();if(activeBriefing)renderReviewPage()});

// Reflow exact source text by measured space without trimming original characters.
let ctExactSource='',ctExactTitle='',ctExactOffsets=[],ctExactQuoteStart=-1;
function ctFitSourcePages(anchor=0){
 const body=$('evidenceBody');body.replaceChildren();const probe=el('span');probe.style.display='block';body.append(probe);
 $('evidencePager').hidden=false;
 const style=getComputedStyle(body),height=Math.max(20,body.clientHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)-2);
 ctSourcePages=[];ctExactOffsets=[];let offset=0;
 while(offset<ctExactSource.length){
  let low=1,high=Math.min(12000,ctExactSource.length-offset),best=1;
  while(low<=high){const count=Math.floor((low+high)/2);probe.textContent=ctExactSource.slice(offset,offset+count)+'\u200b';if(probe.getBoundingClientRect().height<=height){best=count;low=count+1}else high=count-1}
  // Avoid separating a UTF-16 surrogate pair; keep every source character unchanged.
  if(best>1&&/[\uD800-\uDBFF]/.test(ctExactSource[offset+best-1]))best--;
  ctExactOffsets.push(offset);ctSourcePages.push(ctExactSource.slice(offset,offset+best));offset+=best;
 }
 if(!ctSourcePages.length){ctSourcePages=[''];ctExactOffsets=[0]}
 ctSourcePage=Math.max(0,ctExactOffsets.findLastIndex(x=>x<=anchor));renderSourcePage();
}
openPagedText=function(title,text,quote=''){
 ctExactTitle=String(title);ctExactSource=String(text);ctSourceQuote=String(quote||'');ctExactQuoteStart=ctSourceQuote?ctExactSource.indexOf(ctSourceQuote):-1;
 $('evidenceTitle').textContent=ctExactTitle;$('evidenceTitle').title=ctExactTitle;
 if(!$('evidenceDialog').open)$('evidenceDialog').showModal();ctFitSourcePages(Math.max(0,ctExactQuoteStart));
};
renderSourcePage=function(){
 const body=$('evidenceBody'),text=ctSourcePages[ctSourcePage]||'',start=ctExactOffsets[ctSourcePage]||0;body.replaceChildren();
 const from=Math.max(0,ctExactQuoteStart-start),to=Math.min(text.length,ctExactQuoteStart+ctSourceQuote.length-start);
 if(ctExactQuoteStart>=0&&to>from)body.append(document.createTextNode(text.slice(0,from)),el('mark',text.slice(from,to)),document.createTextNode(text.slice(to)));else body.textContent=text;
 setPager('evidencePager',ctSourcePage,ctSourcePages.length);
};
let ctSourceResize;
addEventListener('resize',()=>{clearTimeout(ctSourceResize);if($('evidenceDialog').open)ctSourceResize=setTimeout(()=>ctFitSourcePages(ctExactOffsets[ctSourcePage]||0),100)});

// Search results use the same bounded detail view, including on phone layouts.
let ctSearchResults=[],ctSearchIndex=0;
const ctSearchDialog=el('dialog');ctSearchDialog.id='searchResultsDialog';
const ctSearchHead=el('div',undefined,'sectionhead');ctSearchHead.append(el('h2','Search your sources'));
const ctSearchClose=el('button','Close','quiet');ctSearchClose.onclick=()=>ctSearchDialog.close();ctSearchHead.append(ctSearchClose);
const ctSearchForm=el('form');ctSearchForm.id='exactSearchForm';const ctSearchInput=el('input');ctSearchInput.id='exactSearchQuery';ctSearchInput.placeholder='Search exact words';ctSearchInput.required=true;ctSearchInput.setAttribute('aria-label','Words to find');const ctSearchSubmit=el('button','Find matches');ctSearchSubmit.type='submit';ctSearchForm.append(ctSearchInput,ctSearchSubmit);
const ctSearchStatus=el('p','Find exact wording in the current project.','note');ctSearchStatus.setAttribute('role','status');const ctSearchResult=el('div');ctSearchResult.id='exactSearchResult';
function ctRenderSearch(){ctSearchResult.replaceChildren();const m=ctSearchResults[ctSearchIndex];if(m){ctSearchResult.append(el('h3',m.title),el('p',m.revision+' · line '+m.line,'note'),el('p',m.quote.length>220?m.quote.slice(0,217)+'…':m.quote));const read=el('button','Open exact source','quiet');read.onclick=()=>{ctSearchDialog.close();openEvidence(m.source_id,m.quote)};ctSearchResult.append(read)}setPager('exactSearchPager',ctSearchIndex,ctSearchResults.length)}
ctSearchForm.onsubmit=e=>{e.preventDefault();busy('Searching exact source lines…',async()=>{ctSearchSubmit.disabled=true;try{const d=await tool('search_evidence',{project_id:current,query:ctSearchInput.value});ctSearchResults=d.matches;ctSearchIndex=0;ctSearchStatus.textContent=d.total_matches+' matching lines found.';ctRenderSearch()}finally{ctSearchSubmit.disabled=false}})};
ctSearchDialog.append(ctSearchHead,ctSearchForm,ctSearchStatus,ctSearchResult,pageControls('exactSearchPager',()=>{ctSearchIndex--;ctRenderSearch()},()=>{ctSearchIndex++;ctRenderSearch()}));document.body.append(ctSearchDialog);
function ctOpenSearch(){ctSearchInput.value=$('query').value;ctSearchDialog.showModal();ctSearchInput.focus()}
$('search').onclick=ctOpenSearch;
document.querySelector('.source-rail details>summary').onclick=e=>{e.preventDefault();ctOpenSearch()};
const ctSearchMobile=el('button','Search sources','quiet');ctSearchMobile.onclick=ctOpenSearch;document.querySelector('.directory-screen .compact-add-source').after(ctSearchMobile);
