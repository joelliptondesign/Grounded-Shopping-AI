import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {allowed,resolveLink,validateManifest,createSnapshot,freshness} from '../snapshot.mjs';
const manifest=()=>({version:1,pages:[{id:'overview',title:'Overview',section:'Overview',source:'docs/PROJECT-STATE.md',classification:'current'}],systemNodes:[],systemEdges:[],galleryEntries:[]});
async function fixture(){const dir=await fs.mkdtemp(path.join(os.tmpdir(),'explorer-test-'));await fs.mkdir(path.join(dir,'docs/explorer'),{recursive:true});await fs.writeFile(path.join(dir,'docs/explorer/manifest.json'),JSON.stringify(manifest()));return dir;}
test('source boundary rejects traversal, hidden, credentials and unsupported files',()=>{
 for(const source of ['../outside.md','.env','docs/../README.md','docs/.private.md','docs/credentials.json','/etc/passwd','frontend/image.png','docs/logs/a.txt'])assert.equal(allowed(source),false,source);
 assert.equal(allowed('engine/decision.py'),true);
 assert.deepEqual(resolveLink('api/README.md','../engine/decision.py#symbol'),{source:'engine/decision.py',anchor:'symbol'});
 assert.ok(resolveLink('api/README.md','../../outside.md').error);
 assert.ok(resolveLink('api/README.md','javascript:alert(1)').error);
});
test('manifest requires unique pages and rejects incomplete system nodes',()=>{
 const m=manifest();validateManifest(m);m.pages.push({...m.pages[0]});assert.throws(()=>validateManifest(m),/Duplicate/);
 const n=manifest();n.systemNodes=[{id:'x'}];assert.throws(()=>validateManifest(n),/Invalid system node/);
});
test('snapshot escapes raw HTML, renders tables and diagrams, routes links, and detects changes',async t=>{
 const dir=await fixture();t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 await fs.writeFile(path.join(dir,'docs/PROJECT-STATE.md'),'# Project\n\n## A heading\n\n<script>alert(1)</script>\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n[API](../api/README.md)\n[Missing](missing.md)\n\n```mermaid\nflowchart LR\nA --> B\n```');
 await fs.mkdir(path.join(dir,'api'));await fs.writeFile(path.join(dir,'api/README.md'),'# API\n');
 const s=await createSnapshot(dir),html=s.sources['docs/PROJECT-STATE.md'].html;
 assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;'));assert(html.includes('<table>'));assert(html.includes('mermaid-source'));assert(html.includes('id="a-heading"'));assert(html.includes('source=api%2FREADME.md'));assert(html.includes('unavailable='));assert(html.includes('source=api%2FREADME.md&amp;page=overview'));assert(html.includes('page=overview'));
 assert.equal((await freshness(s,dir)).stale,false);
 await fs.writeFile(path.join(dir,'api/README.md'),'# Changed');assert((await freshness(s,dir)).changed.includes('api/README.md'));
 const next=await createSnapshot(dir);assert.notEqual(next.metadata.snapshotId,s.metadata.snapshotId);
 await fs.writeFile(path.join(dir,'docs/missing.md'),'# Added');assert((await freshness(next,dir)).changed.includes('docs/missing.md'));
});
test('required missing or symlink sources fail; optional links remain visible diagnostics',async t=>{
 const dir=await fixture();t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 await assert.rejects(()=>createSnapshot(dir),/ENOENT/);
 await fs.writeFile(path.join(dir,'docs/other.md'),'# Other');await fs.symlink('other.md',path.join(dir,'docs/PROJECT-STATE.md'));
 await assert.rejects(()=>createSnapshot(dir),/Symlink/);
});
test('current search metadata distinguishes historical and proposed direct sources',async t=>{
 const dir=await fixture();t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 await fs.mkdir(path.join(dir,'docs/history'));await fs.writeFile(path.join(dir,'docs/history/old.md'),'# Old');
 await fs.writeFile(path.join(dir,'docs/proposed.md'),'# Choice\nStatus: Proposed');
 await fs.writeFile(path.join(dir,'docs/PROJECT-STATE.md'),'# Project\n[Old](history/old.md) [Choice](proposed.md)');
 const s=await createSnapshot(dir);assert.equal(s.sources['docs/history/old.md'].classification,'historical');assert.equal(s.sources['docs/proposed.md'].classification,'proposed');
});

test('system references validate cross-links and fail on missing anchors or implementation',async t=>{
 const dir=await fixture();t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 const m=manifest();m.systemNodes=[{id:'receive',label:'Receive',group:'live',documentation:{path:'docs/PROJECT-STATE.md',anchor:'responsibility'},implementation:[{path:'api/server.py',symbol:'def take_turn'}],relatedPages:['overview']}];
 m.systemEdges=[{from:'receive',to:'receive',label:'Context',source:{path:'docs/PROJECT-STATE.md'}}];
 await fs.mkdir(path.join(dir,'api'));await fs.writeFile(path.join(dir,'api/server.py'),'# API\ndef take_turn(): pass');await fs.writeFile(path.join(dir,'docs/PROJECT-STATE.md'),'# Project\n## Responsibility\nOwn the request.');await fs.writeFile(path.join(dir,'docs/explorer/manifest.json'),JSON.stringify(m));
 const s=await createSnapshot(dir);assert.equal(s.systemNodes[0].implementation[0].line,2);assert(s.metadata.hashes['api/server.py']);
 await fs.unlink(path.join(dir,'api/server.py'));await assert.rejects(()=>createSnapshot(dir),/ENOENT/);await fs.writeFile(path.join(dir,'api/server.py'),'# API\ndef take_turn(): pass');
 m.systemEdges[0].to='missing';assert.throws(()=>validateManifest(m),/Invalid system edge/);m.systemEdges[0].to='receive';m.systemNodes[0].documentation.anchor='missing';await fs.writeFile(path.join(dir,'docs/explorer/manifest.json'),JSON.stringify(m));await assert.rejects(()=>createSnapshot(dir),/Missing system documentation anchor/);
});

test('gallery validates explicit fixtures, hashes renderer/assets, and rejects missing examples',async t=>{
 const dir=await fixture();t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 const m=manifest();m.galleryEntries=[{id:'replies',label:'Replies',renderer:{path:'frontend/Rufus Shopping Agent.dc.html'},contract:{path:'frontend/preview-contract.js'},adapter:{path:'frontend/renderer.js'},data:{path:'docs/explorer/examples.json'},exampleIds:['three']}];
 await fs.writeFile(path.join(dir,'docs/PROJECT-STATE.md'),'# Project');await fs.mkdir(path.join(dir,'frontend/products'),{recursive:true});
 for(const file of ['Rufus Shopping Agent.dc.html','preview-contract.js','renderer.js','support.js','image-slot.js'])await fs.writeFile(path.join(dir,'frontend',file),'// fixture runtime source');
 await fs.writeFile(path.join(dir,'frontend/products/polar.png'),Buffer.from('fixture image'));
 const data={provenance:'Synthetic test input',examples:[{id:'three',label:'Three replies',description:'Inspect three replies.',products:[],blocks:[{kind:'suggest',items:['A','B','C']}]}]};
 await fs.writeFile(path.join(dir,'docs/explorer/examples.json'),JSON.stringify(data));await fs.writeFile(path.join(dir,'docs/explorer/manifest.json'),JSON.stringify(m));
 const s=await createSnapshot(dir);assert.equal(s.galleryExamples.three.blocks[0].items.length,3);assert(s.metadata.hashes['frontend/renderer.js']);assert(s.metadata.hashes['frontend/products/polar.png']);assert.equal((await freshness(s,dir)).stale,false);
 await fs.writeFile(path.join(dir,'frontend/products/polar.png'),'changed');assert((await freshness(s,dir)).changed.includes('frontend/products/polar.png'));
 data.examples[0].blocks=[{kind:'recs',more:false,items:[{id:'missing',role:'Option',why:'Reason'}]}];await fs.writeFile(path.join(dir,'docs/explorer/examples.json'),JSON.stringify(data));await assert.rejects(()=>createSnapshot(dir),/Unknown product/);
 data.examples[0].expectedError='Unknown product: missing';await fs.writeFile(path.join(dir,'docs/explorer/examples.json'),JSON.stringify(data));assert((await createSnapshot(dir)).galleryExamples.three.expectedError);
 data.examples[0].expectedError='wrong';await fs.writeFile(path.join(dir,'docs/explorer/examples.json'),JSON.stringify(data));await assert.rejects(()=>createSnapshot(dir),/Expected preview error did not match/);
 data.examples=[];await fs.writeFile(path.join(dir,'docs/explorer/examples.json'),JSON.stringify(data));await assert.rejects(()=>createSnapshot(dir),/Missing gallery example/);
 m.galleryEntries[0].renderer.path='engine/decision.py';assert.throws(()=>validateManifest(m),/Invalid gallery entry/);
});
