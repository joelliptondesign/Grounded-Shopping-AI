import mermaid from 'mermaid';
mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',themeVariables:{fontFamily:'system-ui',primaryColor:'#eeedff',primaryTextColor:'#202337',primaryBorderColor:'#a89ae9',lineColor:'#7a7f99',secondaryColor:'#edf2ff',secondaryTextColor:'#202337',secondaryBorderColor:'#a4b5ee',tertiaryColor:'#f6f7fb',tertiaryTextColor:'#202337',tertiaryBorderColor:'#d6d9e8',background:'#ffffff',mainBkg:'#eeedff',nodeBorder:'#a89ae9',clusterBkg:'#f6f7fb',clusterBorder:'#d6d9e8',edgeLabelBackground:'#ffffff',textColor:'#202337',titleColor:'#202337',actorBkg:'#eeedff',actorBorder:'#a89ae9',actorTextColor:'#202337',signalColor:'#7a7f99',signalTextColor:'#202337',noteBkgColor:'#edf2ff',noteBorderColor:'#a4b5ee',noteTextColor:'#202337',labelBoxBkgColor:'#eeedff',labelBoxBorderColor:'#a89ae9',labelTextColor:'#202337',loopTextColor:'#202337',activationBkgColor:'#edf2ff',activationBorderColor:'#a4b5ee' },suppressErrorRendering:true});
const $=selector=>document.querySelector(selector);
let galleryFrame=null,galleryExample=null,galleryReady=false,galleryTimer=null,galleryProbe=null;
let snapshot, currentPage, downloadText='', downloadName='source.txt', diagramSerial=0, renderSerial=0, polling=false;
const text=(tag,value,className)=>{const node=document.createElement(tag);node.textContent=value;if(className)node.className=className;return node;};
const route=(page,anchor)=>'#'+new URLSearchParams(anchor?{page,anchor}:{page});
function notice(message=''){ $('#notice').textContent=message; }
function closeMenu(){ $('#sidebar').classList.remove('open');$('#menu').setAttribute('aria-expanded','false'); }
function metadata(){
 const m=snapshot.metadata;
 $('#snapshot-meta').replaceChildren(text('div',m.revision==='Unavailable'?'Revision unavailable':m.revision.slice(0,8)),text('div',m.dirty===null?'Local change status unavailable':m.dirty?'Working tree has changes':'Clean working tree'),text('div',new Date(m.generatedAt).toLocaleString()));
}
function navigation(){
 const nav=$('#doc-nav');nav.replaceChildren();
 const sections=[...new Set(snapshot.pages.filter(p=>p.id!=='overview').map(p=>p.section))];
 for(const section of sections){
  const group=document.createElement('details');group.open=['Project','Architecture','Getting started'].includes(section);
  group.append(text('summary',section));
  for(const page of snapshot.pages.filter(p=>p.section===section&&p.id!=='overview')){
   const link=text('a',page.title);link.href=route(page.id);link.dataset.page=page.id;group.append(link);
  }
  nav.append(group);
 }
}
function selectedNavigation(page,section){
 document.querySelectorAll('#navigation a').forEach(link=>link.removeAttribute('aria-current'));
 const key=section|| (page?.id==='overview'?'overview':'docs');
 document.querySelector(`[data-nav="${key}"]`)?.setAttribute('aria-current','page');
 const link=document.querySelector(`[data-page="${page?.id}"]`);if(link){link.setAttribute('aria-current','page');link.parentElement.open=true;}
}
async function diagrams(serial){
 for(const pre of document.querySelectorAll('#content .mermaid-source')){
  const wrapper=pre.parentElement, source=pre.textContent;
  try {
   if(/%%\{|^---/m.test(source))throw Error('Diagram configuration directives are not supported');
   const result=await mermaid.render('diagram-'+ ++diagramSerial,source);
   if(serial!==renderSerial)return;
   const template=document.createElement('template');template.innerHTML=result.svg;
   // Strict Mermaid sanitizes labels. Remove navigation/event-bearing SVG nodes as an additional boundary.
   template.content.querySelectorAll('script,foreignObject script,a').forEach(n=>n.remove());
   template.content.querySelectorAll('*').forEach(node=>{for(const attr of [...node.attributes])if(/^on/i.test(attr.name))node.removeAttribute(attr.name);});
   wrapper.replaceChildren(template.content);
  } catch(error){if(serial!==renderSerial)return;wrapper.prepend(text('p','Diagram could not render; source is shown below. '+error.message,'diagram-error'));}
 }
}
function documentPage(page,anchor){
 currentPage=page;$('#source-button').disabled=false;
 const source=snapshot.sources[page.source];
 $('#breadcrumb').textContent=page.id==='overview'?'Overview':`Documentation / ${page.section}`;
 $('#page-meta').replaceChildren(text('span',source.classification,'badge '+source.classification),text('span','Maintained documentation'),text('span',page.source));
 $('#content').innerHTML=source.html;
 document.title=page.title+' · Grounded Shopping AI';
 selectedNavigation(page);
 $('#outline').replaceChildren(text('h2','On this page'));
 for(const heading of source.headings.filter(h=>h.level===2)){
  const link=text('a',heading.title);link.href=route(page.id,heading.id);$('#outline').append(link);
 }
 const serial=++renderSerial;
 window.scrollTo(0,0);
 diagrams(serial).then(()=>{if(serial===renderSerial&&anchor){const target=document.getElementById(anchor);if(target&&$('#content').contains(target))target.scrollIntoView();else notice('This heading is not present in the current snapshot.');}});
}
function systemRoute(node,view='live'){return '#'+new URLSearchParams({section:'system',view,...(node?{node}:{})});}
function sourceLink(reference,node,view){const a=text('a',reference.path+(reference.symbol?' · '+reference.symbol:'')+(reference.line?' · line '+reference.line:''));a.href='#'+new URLSearchParams({section:'system',view,node,source:reference.path});return a;}
function systemPage(params){
 ++renderSerial;currentPage=null;$('#source-button').disabled=true;selectedNavigation(null,'system');$('#breadcrumb').textContent='System';document.title='System · Grounded Shopping AI';$('#outline').replaceChildren();
 $('#page-meta').replaceChildren(text('span','Architecture','badge'));
 const content=$('#content');content.replaceChildren(text('h1','How the system fits together'));
 content.append(text('p','Follow a message through the system. Choose a part to see what it does, how it connects, and where it lives in the code.'));
 const view=params.get('view')==='demo'?'demo':'live',tabs=text('nav','','system-tabs');tabs.setAttribute('aria-label','System views');
 for(const [id,label] of [['live','Live'],['demo','Demo']]){const a=text('a',label);a.href=systemRoute(null,id);if(view===id)a.setAttribute('aria-current','page');tabs.append(a);}content.append(tabs);
 content.append(text('p',view==='live'?'The Live path includes conversation handling, product selection, and response delivery.':'Demo runs the scripted shopping experience in the browser.','system-boundary'));
 const nodes=snapshot.systemNodes.filter(n=>view==='demo'?n.group==='demo':n.group!=='demo');
 const selected=nodes.find(n=>n.id===params.get('node'))||nodes[0];
 if(!selected){content.append(text('p','No system entries are available in this snapshot.'));return;}
 if(params.has('node')&&!nodes.some(n=>n.id===params.get('node')))notice('This node is not available in the selected view.');
 const layout=text('div','','system-layout'),map=text('nav','','system-map');map.setAttribute('aria-label','System parts');
 for(const group of view==='demo'?['demo']:['live','evidence','presentation']){
  map.append(text('h2',group==='live'?'Live conversation':group==='evidence'?'Catalog and reviews':group==='presentation'?'UI assets':'Browser Demo'));
  for(const n of nodes.filter(n=>n.group===group)){const a=text('a',n.label,'system-node');a.href=systemRoute(n.id,view);if(n.id===selected.id)a.setAttribute('aria-current','true');map.append(a);}
 }
 const detail=text('section','','system-detail');detail.setAttribute('aria-label','Selected system part');detail.append(text('h2',selected.label));
 const doc=snapshot.sources[selected.documentation.path];
 const page=snapshot.pages.find(p=>p.source===selected.documentation.path);
 let excerpt=doc.text;
 if(selected.documentation.anchor){const heading=doc.headings.find(h=>h.id===selected.documentation.anchor);const lines=doc.text.split('\n');const start=lines.findIndex(l=>l.replace(/^#+\s*/, '')===heading.title);let end=lines.findIndex((l,i)=>i>start&&/^## /.test(l));if(end<0)end=lines.length;excerpt=lines.slice(start+1,end).join('\n');}
 const paragraph=excerpt.split(/\n\s*\n/).find(p=>p.trim()&&!p.trim().startsWith('#')&&!p.trim().startsWith('```')&&!p.trim().startsWith('**Owner:'));
 if(paragraph)detail.append(text('p',paragraph.replace(/[`*]/g,''),'responsibility-excerpt'));
 const docLink=text('a','Read more in '+page.title+' →');docLink.href=route(page.id,selected.documentation.anchor);detail.append(docLink);
 detail.append(text('h3','Code'));
 for(const r of selected.implementation)detail.append(sourceLink(r,selected.id,view));
 const connections=snapshot.systemEdges.filter(e=>e.from===selected.id||e.to===selected.id);
 detail.append(text('h3','Relationships'));
 if(!connections.length)detail.append(text('p','This part belongs to the separate browser Demo path.'));
 for(const e of connections){const row=text('div','','system-edge');const otherId=e.from===selected.id?e.to:e.from,other=snapshot.systemNodes.find(n=>n.id===otherId);const a=text('a',(e.from===selected.id?'To ':'From ')+other.label);a.href=systemRoute(other.id,other.group==='demo'?'demo':'live');row.append(a,text('p',e.label));const evidence=text('a','Read more');const ep=snapshot.pages.find(p=>p.source===e.source.path);evidence.href=route(ep.id,e.source.anchor);row.append(evidence);detail.append(row);}
 detail.append(text('h3','Related documentation'));
 for(const id of selected.relatedPages){const p=snapshot.pages.find(p=>p.id===id),a=text('a',p.title);a.href=route(id);detail.append(a);}
 layout.append(map,detail);content.append(layout);window.scrollTo(0,0);
}
function galleryRoute(entry,example){return '#'+new URLSearchParams({section:'gallery',entry,example});}
function probeGallery(){
 clearInterval(galleryProbe);clearTimeout(galleryTimer);
 galleryProbe=setInterval(()=>{if(!galleryFrame?.isConnected||galleryReady){clearInterval(galleryProbe);return;}galleryFrame.contentWindow.postMessage({type:'rufus-preview:ping'},location.origin);},500);
 galleryTimer=setTimeout(()=>{clearInterval(galleryProbe);if(!galleryReady&&$('#gallery-events'))$('#gallery-events').textContent='The local renderer has not started. Use Reset example to retry.';},15000);
}
function loadGalleryExample(){
 if(!galleryFrame||!galleryReady||!galleryExample)return;
 $('#gallery-events').textContent='Loading example…';
 galleryFrame.contentWindow.postMessage({type:'rufus-preview:load',example:galleryExample},location.origin);
}
function galleryPage(params){
 ++renderSerial;currentPage=null;$('#source-button').disabled=true;selectedNavigation(null,'gallery');$('#breadcrumb').textContent='UI Gallery';document.title='UI Gallery · Grounded Shopping AI';$('#outline').replaceChildren();
 $('#page-meta').replaceChildren(text('span','Component patterns','badge'));
 const content=$('#content');
 const entries=snapshot.galleryEntries,entry=entries.find(g=>g.id===params.get('entry'))||entries[0];
 if(!entry){content.replaceChildren(text('p','No gallery entries in this snapshot.'));return;}
 const exampleId=entry.exampleIds.includes(params.get('example'))?params.get('example'):entry.exampleIds[0];const previousExample=galleryExample?.id;galleryExample=snapshot.galleryExamples[exampleId];
 if(galleryFrame?.isConnected&&galleryFrame.dataset.snapshot===snapshot.metadata.snapshotId&&$('#gallery-example')){
   const select=$('#gallery-example');select.replaceChildren();for(const id of entry.exampleIds){const option=text('option',snapshot.galleryExamples[id].label);option.value=id;option.selected=id===exampleId;select.append(option);}select.onchange=()=>{location.hash=galleryRoute(entry.id,select.value);};
   document.querySelectorAll('[aria-label="Gallery patterns"] a').forEach(a=>{a.removeAttribute('aria-current');if(new URLSearchParams(a.hash.slice(1)).get('entry')===entry.id)a.setAttribute('aria-current','page');});
   $('.gallery-info h2').textContent=galleryExample.label;$('.example-description').textContent=galleryExample.description;$('.example-provenance').textContent=galleryExample.provenance;
   const refs=[entry.renderer,entry.adapter,entry.contract,entry.data];document.querySelectorAll('.gallery-info>a').forEach((a,i)=>{a.href='#'+new URLSearchParams({section:'gallery',entry:entry.id,example:exampleId,source:refs[i].path});});
   $('.gallery-info details pre').textContent=JSON.stringify({id:galleryExample.id,products:galleryExample.products,blocks:galleryExample.blocks},null,2);
   if(previousExample!==exampleId)loadGalleryExample();return;
 }
 content.replaceChildren(text('h1','UI Gallery'),text('p','Browse the shopping interface, try its interactions, and inspect the code and data behind each example.'));
 const tabs=text('nav','','system-tabs');tabs.setAttribute('aria-label','Gallery patterns');
 for(const g of entries){const a=text('a',g.label);a.href=galleryRoute(g.id,g.exampleIds[0]);if(g.id===entry.id)a.setAttribute('aria-current','page');tabs.append(a);}content.append(tabs);
 const controls=text('div','','gallery-controls'),label=text('label','Example '),select=document.createElement('select');select.id='gallery-example';
 for(const id of entry.exampleIds){const option=text('option',snapshot.galleryExamples[id].label);option.value=id;option.selected=id===exampleId;select.append(option);}label.append(select);controls.append(label);
 select.onchange=()=>{location.hash=galleryRoute(entry.id,select.value);};
 const reset=text('button','Reset example','refresh');reset.onclick=()=>{if(galleryReady)loadGalleryExample();else{$('#gallery-events').textContent='Retrying local renderer…';galleryFrame.src='/preview/renderer.html?preview=1';probeGallery();}};controls.append(reset);
 const empty=text('button','Clear preview','quiet');empty.onclick=()=>{if(galleryReady)galleryFrame.contentWindow.postMessage({type:'rufus-preview:load',example:{id:'empty',products:[],blocks:[]}},location.origin);};controls.append(empty);content.append(controls);
 const layout=text('div','','gallery-layout'),preview=text('section','','gallery-preview');preview.setAttribute('aria-label','Rendered example');
 galleryReady=false;galleryFrame=document.createElement('iframe');galleryFrame.dataset.snapshot=snapshot.metadata.snapshotId;galleryFrame.title='Actual shopper renderer';galleryFrame.src='/preview/renderer.html?preview=1';preview.append(galleryFrame);
 const currentFrame=galleryFrame;const observer=new ResizeObserver(()=>{if(!currentFrame.isConnected){observer.disconnect();return;}const scale=Math.min(1,preview.clientWidth/450);currentFrame.style.transform='scale('+scale+')';preview.style.height=925*scale+'px';});observer.observe(preview);
 const info=text('section','','gallery-info');info.append(text('h2',galleryExample.label),text('p',galleryExample.description,'example-description'));
 const events=text('pre','Waiting for renderer…','gallery-events');events.id='gallery-events';events.setAttribute('role','status');info.append(text('h3','Interactions'),events);
 probeGallery();
 info.append(text('h3','Explore this pattern'));
 for(const [name,r] of [['View code',entry.renderer],['View rendering logic',entry.adapter],['View data contract',entry.contract],['View examples',entry.data]]){const a=text('a',name+' →');a.href='#'+new URLSearchParams({section:'gallery',entry:entry.id,example:exampleId,source:r.path});info.append(a);}
 const details=document.createElement('details');details.append(text('summary','Inspect input'));const data=text('pre',JSON.stringify({id:galleryExample.id,products:galleryExample.products,blocks:galleryExample.blocks},null,2));details.append(data);info.append(details);
 const about=document.createElement('details');about.append(text('summary','About this example'),text('p',galleryExample.provenance,'example-provenance'));info.append(about);
 layout.append(preview,info);content.append(layout);window.scrollTo(0,0);
}
window.addEventListener('message',event=>{
 if(!galleryFrame||event.source!==galleryFrame.contentWindow||event.origin!==location.origin||event.data?.type!=='rufus-preview:event')return;
 const output=$('#gallery-events');if(!output)return;
 if(event.data.action==='ready'){if(galleryReady)return;galleryReady=true;clearTimeout(galleryTimer);clearInterval(galleryProbe);loadGalleryExample();return;}
 const d=event.data.details;
 const actions={cart:'Add to cart · '+(galleryExample.products.find(p=>p.id===d.id)?.name||d.id),more:'See more · '+d.role,reply:'Selected reply · '+d.text,feedback:'Feedback · '+(d.value==='up'?'Helpful':'Not helpful')};
 output.textContent=event.data.action==='loaded'?'Ready to explore':event.data.action==='error'?'Example error: '+d.message:actions[event.data.action]||'This action is unavailable in the gallery.';
});
function openSource(source){
 const value=snapshot.sources[source];
 $('#source-title').textContent='Repository source';
 $('#source-info').replaceChildren(text('div',source),text('div',value?`${value.classification} · snapshot ${snapshot.metadata.snapshotId.slice(0,12)}`:'Unavailable source'));
 if(value){$('#source-info').append(text('div','SHA-256: '+snapshot.metadata.hashes[source]));downloadText=value.text;downloadName=source.split('/').pop();}
 $('#source-text').textContent=value?.text||snapshot.diagnostics[source]||'This path is not included in the curated snapshot.';
 $('#download-source').hidden=!value;
 if(!$('#source-dialog').open)$('#source-dialog').showModal();
}
function showSnapshot(){
 $('#source-title').textContent='Snapshot provenance';
 $('#source-info').replaceChildren(text('div','Files and versions used by the explorer. Includes your local edits.'));
 downloadText=JSON.stringify(snapshot.metadata,null,2);downloadName='explorer-snapshot-metadata.json';$('#source-text').textContent=downloadText;$('#download-source').hidden=false;$('#source-dialog').showModal();
}
function renderRoute(){
 if(!snapshot)return;
 notice();closeMenu();
 const params=new URLSearchParams(location.hash.slice(1));
 if(params.has('source')&&params.get('section')==='gallery'){galleryPage(params);openSource(params.get('source'));return;}
 if(params.has('source')&&params.get('section')==='system'){systemPage(params);openSource(params.get('source'));return;}
 if(params.has('source')){documentPage(snapshot.pages.find(p=>p.id===params.get('page'))||snapshot.pages.find(p=>p.id===currentPage?.id)||snapshot.pages.find(p=>p.id==='overview')||snapshot.pages[0]);openSource(params.get('source'));return;}
 if($('#source-dialog').open)$('#source-dialog').close();
 if(params.has('unavailable')){documentPage(snapshot.pages.find(p=>p.id===params.get('page'))||snapshot.pages[0]);notice(`Cannot open “${params.get('unavailable')}”: ${params.get('reason')||'Source not available in this snapshot'}.`);return;}
 if(params.get('section')==='system'){systemPage(params);return;}
 if(params.get('section')==='gallery'){galleryPage(params);return;}
 const page=snapshot.pages.find(p=>p.id===(params.get('page')||'overview'));
 if(!page){notice('This page is not in the current explorer manifest.');documentPage(snapshot.pages[0]);return;}
 documentPage(page,params.get('anchor'));
}
function search(){
 const query=$('#search').value.trim().toLowerCase(),results=$('#results');results.replaceChildren();results.hidden=!query;$('#navigation').hidden=Boolean(query);if(!query)return;
 const terms=query.split(/\s+/);
 const matches=snapshot.pages.filter(p=>p.classification==='current' && terms.every(term=>(p.title+' '+snapshot.sources[p.source].text).toLowerCase().includes(term)));
 const galleryMatches=snapshot.galleryEntries.filter(g=>terms.every(term=>(g.label+' '+g.exampleIds.map(id=>snapshot.galleryExamples[id].label).join(' ')).toLowerCase().includes(term)));
 for(const g of galleryMatches){const a=text('a',g.label+' · UI Gallery');a.href=galleryRoute(g.id,g.exampleIds[0]);a.onclick=()=>{$('#search').value='';search();};results.append(a);}
 const nodeMatches=snapshot.systemNodes.filter(n=>terms.every(term=>(n.label+' '+n.implementation.map(r=>r.path).join(' ')).toLowerCase().includes(term)));
 for(const n of nodeMatches){const a=text('a',n.label);a.href=systemRoute(n.id,n.group==='demo'?'demo':'live');a.onclick=()=>{$('#search').value='';search();};results.append(a);}
 results.append(text('p',`${galleryMatches.length} gallery patterns · ${nodeMatches.length} system parts · ${matches.length} current document${matches.length===1?'':'s'}`));
 for(const p of matches){const source=snapshot.sources[p.source].text.replace(/<!--[^]*?-->/g,'').replace(/[`#*|]/g,'');const index=Math.max(0,source.toLowerCase().indexOf(terms[0]));const link=document.createElement('a');link.href=route(p.id);link.append(text('strong',p.title),text('p','…'+source.slice(Math.max(0,index-35),index+135).replace(/\s+/g,' ')+'…'));link.onclick=()=>{$('#search').value='';search();};results.append(link);}
}
async function checkFreshness(){
 if(!snapshot||polling||document.hidden)return;polling=true;
 try {const response=await fetch('/api/freshness');if(!response.ok)throw Error();const state=await response.json();const stale=state.stale||state.snapshotId!==snapshot.metadata.snapshotId;$('#freshness').hidden=!stale;$('#freshness').textContent=stale?`Repository files have changed${state.changed.length?` (${state.changed.length} included source${state.changed.length===1?'':'s'})`:''}. Refresh to load the latest version.`:'';}
 catch{$('#freshness').hidden=false;$('#freshness').textContent='Freshness cannot be checked. The local server may be stopped; you are reading the last loaded snapshot.';}
 finally{polling=false;}
}
$('.skip').onclick=event=>{event.preventDefault();$('#reading').focus();$('#reading').scrollIntoView();};
$('#search').addEventListener('input',search);
$('#menu').onclick=()=>{const open=$('#sidebar').classList.toggle('open');$('#menu').setAttribute('aria-expanded',String(open));};
$('#source-button').onclick=()=>{if(currentPage)location.hash=new URLSearchParams({source:currentPage.source,page:currentPage.id});};
$('#snapshot-details').onclick=showSnapshot;
$('#close-source').onclick=()=>$('#source-dialog').close();
$('#source-dialog').addEventListener('close',()=>{if(new URLSearchParams(location.hash.slice(1)).has('source')){const params=new URLSearchParams(location.hash.slice(1));params.delete('source');history.replaceState(null,'',['system','gallery'].includes(params.get('section'))?'#'+params:route(currentPage?.id||'overview')); }});
$('#download-source').onclick=()=>{const url=URL.createObjectURL(new Blob([downloadText],{type:'text/plain'}));const link=document.createElement('a');link.href=url;link.download=downloadName;link.click();URL.revokeObjectURL(url);};
$('#refresh').onclick=async()=>{const button=$('#refresh');button.disabled=true;notice('Refreshing from repository sources…');try{const response=await fetch('/api/refresh',{method:'POST'});const result=await response.json();if(!response.ok)throw Error(result.error);snapshot=result;metadata();navigation();renderRoute();search();$('#freshness').hidden=true;notice('Updated from the repository.');}catch(error){notice('Refresh failed: '+error.message+'. The previous snapshot remains available.');}finally{button.disabled=false;}};
window.addEventListener('hashchange',renderRoute);
window.addEventListener('focus',checkFreshness);
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu();});
try{const response=await fetch('/api/snapshot');if(!response.ok)throw Error('Snapshot could not load');snapshot=await response.json();metadata();navigation();renderRoute();checkFreshness();setInterval(checkFreshness,15000);}catch(error){$('#content').replaceChildren(text('h1','Explorer unavailable'),text('p',error.message));}
