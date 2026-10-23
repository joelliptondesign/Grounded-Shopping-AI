import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {localPreviewHtml,localRuntimeFiles} from './preview-runtime.mjs';
import { buildShell } from './build.mjs';
import { createSnapshot, freshness } from './snapshot.mjs';
const port=Number(process.env.EXPLORER_PORT||8766);
const output=await buildShell();
let snapshot=await createSnapshot();
let shoppingApiAttempts=0;
const json=(res,status,value)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{
  // Loopback binding plus exact Host/Origin prevents DNS rebinding and cross-site refresh.
  const hosts=new Set(['127.0.0.1:'+port,'localhost:'+port]);
  if(!hosts.has(req.headers.host)) return json(res,403,{error:'Local host required'});
  if(req.headers.origin && !['http://127.0.0.1:'+port,'http://localhost:'+port].includes(req.headers.origin)) return json(res,403,{error:'Same-origin request required'});
  try {
    const url=new URL(req.url,'http://localhost');
    if(/^\/api\/session(?:\/|$)/.test(url.pathname))shoppingApiAttempts++;
    if(req.method==='GET'&&url.pathname==='/api/preview-audit')return json(res,200,{shoppingApiAttempts});
    if(req.method==='GET' && url.pathname==='/api/snapshot') return json(res,200,snapshot);
    if(req.method==='GET' && url.pathname==='/api/freshness') return json(res,200,await freshness(snapshot));
    if(req.method==='POST' && url.pathname==='/api/refresh') {
      const next=await createSnapshot(); snapshot=next; return json(res,200,snapshot);
    }
    if(req.method!=='GET') return json(res,405,{error:'Unsupported method'});
    if(Object.hasOwn(localRuntimeFiles,url.pathname)||url.pathname==='/preview/runtime-resources.js'){
      res.writeHead(200,{'Content-Type':url.pathname.endsWith('.woff2')?'font/woff2':'text/javascript','Cache-Control':'public, max-age=3600','X-Content-Type-Options':'nosniff'});return res.end(await fs.readFile(path.join(output,url.pathname.split('/').pop())));
    }
    if(url.pathname==='/source'){
      const name=url.searchParams.get('path');if(!Object.hasOwn(snapshot.sources,name))return json(res,404,{error:'Source is not included in this snapshot'});
      const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      const source=snapshot.sources[name],rows=source.text.split('\n').map((line,i)=>`<div class="line" id="L${i+1}"><a href="#L${i+1}">${i+1}</a><code>${escape(line)}</code></div>`).join('');
      res.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'"});return res.end(`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(name)} · Source</title><link rel="stylesheet" href="/design-system/source-view.css"><header><h1>${escape(name)}</h1><p>Inspected repository snapshot · ${escape(snapshot.metadata.revision.slice(0,8))} · ${escape(snapshot.metadata.generatedAt)}</p></header><main>${rows}</main></html>`);
    }
    const previewFiles={'/preview/renderer.html':'frontend/Rufus Shopping Agent.dc.html','/preview/renderer.js':'frontend/renderer.js','/preview/preview-contract.js':'frontend/preview-contract.js','/preview/support.js':'frontend/support.js','/preview/image-slot.js':'frontend/image-slot.js'};
    if(previewFiles[url.pathname]){
      if(url.pathname==='/preview/renderer.html'&&url.searchParams.get('preview')!=='1')return json(res,400,{error:'Explicit preview mode required'});
      const source=snapshot.sources[previewFiles[url.pathname]];if(!source)return json(res,404,{error:'Preview is not included'});
      res.writeHead(200,{'Content-Type':url.pathname.endsWith('.html')?'text/html':'text/javascript','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'none'"});return res.end(url.pathname==='/preview/renderer.html'?localPreviewHtml(source.text):source.text);
    }
    if(url.pathname==='/preview/products/polar.png'){
      res.writeHead(200,{'Content-Type':'image/png','Cache-Control':'no-store'});return res.end(Buffer.from(snapshot.previewAssets['frontend/products/polar.png'],'base64'));
    }
    const file={'/':'index.html','/index.html':'index.html','/client.js':'client.js','/style.css':'style.css','/design-system/workflow-tokens.css':'design-system/workflow-tokens.css','/design-system/explorer-components.css':'design-system/explorer-components.css','/design-system/source-view.css':'design-system/source-view.css'}[url.pathname];
    if(!file)return json(res,404,{error:'Not an explorer resource'});
    res.writeHead(200,{'Content-Type':file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"});
    res.end(await fs.readFile(path.join(output,file)));
  } catch(error){json(res,500,{error:error.message});}
});
server.listen(port,'127.0.0.1',()=>console.log('Explorer: http://localhost:'+port));
for(const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>server.close(async()=>{await fs.rm(output,{recursive:true,force:true});process.exit(0);}));
