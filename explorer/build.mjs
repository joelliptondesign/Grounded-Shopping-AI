import fs from 'node:fs/promises';
import {verifyDesignSystem} from './sync-design-system.mjs';
import os from 'node:os';
import path from 'node:path';
import { build } from 'esbuild';
import {copyPreviewRuntime} from './preview-runtime.mjs';
import { createSnapshot } from './snapshot.mjs';

export async function buildShell() {
  await verifyDesignSystem();
  const output=await fs.mkdtemp(path.join(os.tmpdir(),'shopping-explorer-'));
  await build({entryPoints:[path.join(import.meta.dirname,'client.js')],outfile:path.join(output,'client.js'),bundle:true,format:'esm',splitting:false,minify:true,logLevel:'silent'});
  for (const file of ['index.html','style.css']) await fs.copyFile(path.join(import.meta.dirname,file),path.join(output,file));
  await fs.cp(path.join(import.meta.dirname,'design-system'),path.join(output,'design-system'),{recursive:true});
  await copyPreviewRuntime(output);
  return output;
}
if (process.argv[1]===import.meta.filename) {
  const output=await buildShell();
  await fs.writeFile(path.join(output,'snapshot.json'),JSON.stringify(await createSnapshot()));
  console.log('Built explorer snapshot: '+output);
}
