import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {localPreviewHtml,runtimeResources} from '../preview-runtime.mjs';
import {buildShell} from '../build.mjs';
test('local preview redirects the existing runtime hook and preserves authored renderer source',async t=>{
 const html=await fs.readFile(new URL('../../frontend/Rufus Shopping Agent.dc.html',import.meta.url),'utf8');
 const local=localPreviewHtml(html);assert(local.indexOf('runtime-resources.js')<local.indexOf('./support.js'));assert(!local.includes('fonts.googleapis.com'));assert(local.includes('font-family:Nunito'));assert(local.includes('loadPreview(example)'));
 const context={window:{__resources:{existing:'preserved'}}};vm.runInNewContext(runtimeResources,context);assert.equal(context.window.__resources.existing,'preserved');assert.equal(context.window.__resources['https://unpkg.com/react@18.3.1/umd/react.production.min.js'],'/preview/react.js');
 const output=await buildShell();t.after(()=>fs.rm(output,{recursive:true,force:true}));
 for(const file of ['react.js','react-dom.js','babel.js','nunito.woff2'])assert((await fs.stat(output+'/'+file)).size>1000,file);
});
