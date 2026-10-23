import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import MarkdownIt from 'markdown-it';
import {createRequire} from 'node:module';
const {validate:validateExample}=createRequire(import.meta.url)('../frontend/preview-contract.js');

export const root = path.resolve(import.meta.dirname, '..');
export const manifestPath = 'docs/explorer/manifest.json';
const md = new MarkdownIt({ html: false, linkify: false, typographer: false });
const hash = text => crypto.createHash('sha256').update(text).digest('hex');
const escape = text => md.utils.escapeHtml(text);
const roots = ['docs/', 'frontend/', 'api/', 'engine/', 'tests/', 'scripts/', 'evals/', 'bench/', 'prompts/', 'artifacts/'];
const topFiles = new Set(['README.md', 'README-PORTFOLIO.md', 'GOVERNANCE.md', 'AGENTS.md', 'CLAUDE.md', 'requirements.txt', 'requirements-dev.txt', 'pyproject.toml', 'vercel.json', 'app.py', 'streamlit_app.py', 'explorer/README.md']);
export function allowed(source) {
  if (typeof source !== 'string' || path.posix.isAbsolute(source) || source.includes('\\') || source.split('/').some(p => p === '..' || p.startsWith('.'))) return false;
  if (!topFiles.has(source) && !roots.some(r => source.startsWith(r))) return false;
  if (/(^|\/)(node_modules|__pycache__|logs|cache|sources)(\/|$)/i.test(source) || /(?:secret|credential|\.env)/i.test(source)) return false;
  return /\.(md|py|js|mjs|cjs|json|txt|toml|html)$/.test(source) && !/\.log\./.test(source);
}
export function resolveLink(from, href) {
  if (/^https?:\/\//i.test(href) || /^mailto:/i.test(href)) return { external: href };
  if (/^[a-z][a-z\d+.-]*:/i.test(href) || href.startsWith('//')) return { error: 'Unsupported link protocol' };
  try {
    const [file, ...fragment] = href.split('#');
    if (file.includes('?')) return { error: 'Local links with query parameters are not included' };
    const decoded = decodeURIComponent(file);
    const source = decoded ? path.posix.normalize(path.posix.join(path.posix.dirname(from), decoded)) : from;
    if (decoded.startsWith('/') || !allowed(source)) return { error: 'Source is outside the explorer’s permitted text scope' };
    return { source, anchor: decodeURIComponent(fragment.join('#')) };
  } catch { return { error: 'Invalid link encoding' }; }
}
async function readSource(repo, source) {
  if (!allowed(source)) throw Error('Source is excluded: ' + source);
  const target = path.resolve(repo, source);
  const real = await fs.realpath(target);
  if (!real.startsWith((await fs.realpath(repo)) + path.sep)) throw Error('Source escapes repository: ' + source);
  // Reject symlinks at every level, including links to otherwise permitted locations.
  let current = repo;
  for (const part of source.split('/')) {
    current = path.join(current, part);
    if ((await fs.lstat(current)).isSymbolicLink()) throw Error('Symlink source excluded: ' + source);
  }
  const stat = await fs.stat(target);
  if (!stat.isFile() || stat.size > 512 * 1024) throw Error('Source is not a supported text file: ' + source);
  const text = await fs.readFile(target, 'utf8');
  if (text.includes('\0')) throw Error('Binary source excluded: ' + source);
  return text;
}
async function readPreviewImage(repo,source){
 if(source!=='frontend/products/polar.png')throw Error('Unsupported preview image');
 let current=repo;for(const part of source.split('/')){current=path.join(current,part);if((await fs.lstat(current)).isSymbolicLink())throw Error('Symlink preview image excluded');}
 const real=await fs.realpath(current);if(!real.startsWith((await fs.realpath(repo))+path.sep))throw Error('Preview image escapes repository');
 const stat=await fs.stat(real);if(!stat.isFile()||stat.size>2*1024*1024)throw Error('Unsupported preview image');
 return fs.readFile(real);
}
export function validateManifest(manifest) {
  if (manifest.version !== 1 || !Array.isArray(manifest.pages) || !manifest.pages.length) throw Error('Unsupported or empty explorer manifest');
  const ids = new Set(), sources = new Set();
  for (const p of manifest.pages) {
    if (!p || !/^[a-z0-9-]+$/.test(p.id) || typeof p.title !== 'string' || !p.title || typeof p.section !== 'string' || !['current','proposed','historical','verification'].includes(p.classification) || !allowed(p.source)) throw Error('Invalid manifest page');
    if (ids.has(p.id) || sources.has(p.source)) throw Error('Duplicate page ID or source');
    ids.add(p.id); sources.add(p.source);
  }
  for (const key of ['systemNodes','systemEdges','galleryEntries']) if (!Array.isArray(manifest[key])) throw Error('Missing '+key);

  const nodeIds=new Set();
  const reference=r=>r && allowed(r.path) && (r.anchor===undefined||typeof r.anchor==='string') && (r.symbol===undefined||typeof r.symbol==='string');
  for(const n of manifest.systemNodes){
    if(!n || !/^[a-z0-9-]+$/.test(n.id)||nodeIds.has(n.id)||!n.label||!['live','demo','evidence','presentation'].includes(n.group)||!reference(n.documentation)||!Array.isArray(n.implementation)||!n.implementation.length||!n.implementation.every(reference)||!Array.isArray(n.relatedPages)||!n.relatedPages.every(id=>ids.has(id)))throw Error('Invalid system node');
    nodeIds.add(n.id);
  }
  const galleryIds=new Set();
  for(const g of manifest.galleryEntries){
    if(!g||! /^[a-z0-9-]+$/.test(g.id)||galleryIds.has(g.id)||!g.label||![g.renderer,g.contract,g.adapter,g.data].every(reference)||g.renderer.path!=='frontend/Rufus Shopping Agent.dc.html'||g.contract.path!=='frontend/preview-contract.js'||g.adapter.path!=='frontend/renderer.js'||!Array.isArray(g.exampleIds)||!g.exampleIds.length||new Set(g.exampleIds).size!==g.exampleIds.length)throw Error('Invalid gallery entry');
    galleryIds.add(g.id);
  }
  for(const e of manifest.systemEdges)if(!nodeIds.has(e.from)||!nodeIds.has(e.to)||!e.label||!reference(e.source))throw Error('Invalid system edge');
}
function links(text) {
  const found = [];
  for (const token of md.parse(text, {})) for (const child of token.children || []) {
    if (child.type === 'link_open') found.push(child.attrGet('href'));
    if (child.type === 'image') found.push(child.attrGet('src'));
  }
  return found;
}
function classification(source, text, declared) {
  if (/^Status:\s*(Proposed|Unresolved)/im.test(text)) return 'proposed';
  if (/^(docs\/(history|archive|baseline)\/|frontend\/docs\/)/.test(source)) return 'historical';
  if (/^(docs\/work\/|artifacts\/|bench\/)/.test(source)) return 'verification';
  return declared || 'current';
}
function routeFor(source, anchor, pages, origin) {
  const page = pages.find(p => p.source === source);
  const params = new URLSearchParams(page ? {page: page.id} : {source, page:pages.find(p=>p.source===origin)?.id||'overview'});
  if (anchor) params.set('anchor', anchor);
  return '#' + params;
}
function render(source, text, pages, sources, diagnostics) {
  const parser = new MarkdownIt({html:false});
  const headingCounts = new Map(), headings=[];
  parser.renderer.rules.heading_open = (tokens, index, options, env, self) => {
    const label = tokens[index+1].children?.filter(t => ['text','code_inline'].includes(t.type)).map(t=>t.content).join('') || tokens[index+1].content;
    const base = label.toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu,'').replace(/\s+/g,'-');
    const count=headingCounts.get(base)||0; headingCounts.set(base,count+1);
    const id=base+(count?'-'+count:''); tokens[index].attrSet('id',id);
    headings.push({id,title:label,level:Number(tokens[index].tag.slice(1))});
    return self.renderToken(tokens,index,options);
  };
  parser.renderer.rules.link_open = (tokens, index, options, env, self) => {
    const token=tokens[index], href=token.attrGet('href'), result=resolveLink(source,href);
    if (result.external) { token.attrSet('href',result.external); token.attrSet('target','_blank'); token.attrSet('rel','noopener noreferrer'); }
    else if (result.source && sources[result.source]) token.attrSet('href',routeFor(result.source,result.anchor,pages,source));
    else {
      const reason=result.error || diagnostics[result.source] || 'This linked source is not included in the snapshot';
      token.attrSet('href','#'+new URLSearchParams({unavailable:href,reason,page:pages.find(p=>p.source===source)?.id||'overview'})); token.attrSet('class','unavailable-link');
      token.attrSet('title',reason);
    }
    return self.renderToken(tokens,index,options);
  };
  parser.renderer.rules.image = (tokens,index) => {
    const token=tokens[index];
    return `<span class="image-note">Image reference: ${escape(token.content || 'image')} (${escape(token.attrGet('src') || '')}). Binary images are outside this documentation snapshot.</span>`;
  };
  const fence=parser.renderer.rules.fence;
  parser.renderer.rules.fence = (tokens,index,options,env,self) => tokens[index].info.trim()==='mermaid'
    ? `<div class="diagram"><pre class="mermaid-source">${escape(tokens[index].content)}</pre></div>`
    : fence(tokens,index,options,env,self);
  return {html:parser.render(text.replace(/<!--[\s\S]*?-->/g,'')),headings};
}
export async function createSnapshot(repo=root) {
  const manifestText=await readSource(repo,manifestPath), manifest=JSON.parse(manifestText);
  validateManifest(manifest);
  const sources=Object.create(null), diagnostics=Object.create(null), hashes={[manifestPath]:hash(manifestText)};
  const pages=manifest.pages.map(p=>({...p}));
  for (const p of pages) {
    const text=await readSource(repo,p.source); // Required sources fail the build visibly.
    sources[p.source]={text,classification:classification(p.source,text,p.classification)};
    p.classification=sources[p.source].classification;
  }
  const references=manifest.systemNodes.flatMap(n=>[n.documentation,...n.implementation]).concat(manifest.systemEdges.map(e=>e.source),manifest.galleryEntries.flatMap(g=>[g.renderer,g.contract,g.adapter,g.data]),manifest.galleryEntries.length?[{path:'frontend/support.js'},{path:'frontend/image-slot.js'}]:[]);
  for(const r of references)if(!sources[r.path]){const text=await readSource(repo,r.path);sources[r.path]={text,classification:classification(r.path,text)};}
  // Only direct links from curated pages: no recursive private-folder or evidence scans.
  for (const p of pages) for (const href of links(sources[p.source].text)) {
    const result=resolveLink(p.source,href);
    if (!result.source || sources[result.source] || diagnostics[result.source]) continue;
    try { const text=await readSource(repo,result.source); sources[result.source]={text,classification:classification(result.source,text)}; }
    catch { diagnostics[result.source]='Linked source is missing, excluded, or too large to include'; }
  }
  for (const [source, value] of Object.entries(sources)) {
    hashes[source]=hash(value.text);
    if (source.endsWith('.md')) Object.assign(value,render(source,value.text,pages,sources,diagnostics));
  }
  for(const r of references){
    const value=sources[r.path];
    if(r.anchor && !value.headings?.some(h=>h.id===r.anchor))throw Error('Missing system documentation anchor: '+r.path+'#'+r.anchor);
    if(r.symbol){const index=value.text.split('\n').findIndex(line=>line.includes(r.symbol));if(index<0)throw Error('Missing system symbol: '+r.symbol);r.line=index+1;}
    if(r.focus){if(typeof r.focus.match!=='string'||!r.focus.match||typeof r.focus.explanation!=='string'||!r.focus.explanation)throw Error('Invalid code explanation: '+r.path);const lines=value.text.split('\n'),index=lines.findIndex((line,i)=>i>=(r.line||1)-1&&line.includes(r.focus.match));if(index<0)throw Error('Missing explained code: '+r.path+' '+r.focus.match);r.focus.line=index+1;}
  }
  const previewAssets=Object.create(null);
  if(manifest.galleryEntries.length){const source='frontend/products/polar.png',bytes=await readPreviewImage(repo,source);hashes[source]=hash(bytes);previewAssets[source]=bytes.toString('base64');}
  const galleryExamples=Object.create(null);
  for(const g of manifest.galleryEntries){
    const fixture=JSON.parse(sources[g.data.path].text);
    if(typeof fixture.provenance!=='string'||!Array.isArray(fixture.examples))throw Error('Gallery fixture requires provenance and examples');
    const exampleIds=new Set();
    for(const e of fixture.examples){if(exampleIds.has(e.id)||typeof e.label!=='string'||typeof e.description!=='string'||!e.description)throw Error('Invalid gallery example');exampleIds.add(e.id);
      if(e.expectedError!==undefined){if(typeof e.expectedError!=='string'||!e.expectedError)throw Error('Invalid expected preview error');let error;try{validateExample(e);}catch(failure){error=failure.message;}if(error!==e.expectedError)throw Error('Expected preview error did not match: '+e.id);}
      else validateExample(e);}
    for(const id of g.exampleIds){const example=fixture.examples.find(e=>e.id===id);if(!example)throw Error('Missing gallery example: '+id);galleryExamples[id]={...example,provenance:fixture.provenance};}
  }
  let revision='Unavailable',dirty=null;
  try {
    revision=execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();
    dirty=Boolean(execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim());
  } catch { /* A filesystem snapshot still works without Git metadata. */ }
  const snapshotId=hash(JSON.stringify({revision,hashes}));
  return {version:1,pages,systemNodes:manifest.systemNodes,systemEdges:manifest.systemEdges,galleryEntries:manifest.galleryEntries,galleryExamples,previewAssets,sources,diagnostics,metadata:{revision,dirty,generatedAt:new Date().toISOString(),snapshotId,hashes}};
}
export async function freshness(snapshot,repo=root) {
  const changed=[];
  for (const [source,expected] of Object.entries(snapshot.metadata.hashes)) {
    try { if(hash(await (source==='frontend/products/polar.png'?readPreviewImage(repo,source):readSource(repo,source)))!==expected) changed.push(source); }
    catch { changed.push(source); }
  }
  // A formerly missing direct link becoming available also requires refresh.
  for (const source of Object.keys(snapshot.diagnostics)) {
    try { await readSource(repo,source); changed.push(source); } catch {}
  }
  let revision=snapshot.metadata.revision,dirty=snapshot.metadata.dirty;
  try {
    revision=execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();
    dirty=Boolean(execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim());
  } catch {}
  return {snapshotId:snapshot.metadata.snapshotId,stale:changed.length>0||revision!==snapshot.metadata.revision||dirty!==snapshot.metadata.dirty,changed,revision,dirty};
}
