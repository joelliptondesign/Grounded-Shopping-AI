import { readFileSync, readdirSync, lstatSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, relative, isAbsolute, sep } from 'node:path';
import validators from './validators.cjs';
export const hash = value => createHash('sha256').update(value).digest('hex');
const home = new URL('./',import.meta.url);
const names = readdirSync(new URL('schemas/',home)).filter(n=>n.endsWith('.json')).sort();
const actual = hash(JSON.stringify(names.map(n=>[n,readFileSync(new URL('schemas/'+n,home),'utf8')])));
if(actual!==validators.schemaDigest) throw Error('Schema validators are stale. Rebuild with npm ci && npm run build in core/groundwork. This blocks this check, not unrelated work.');
export function validate(kind,value) {
 const fn=validators[kind];
 if(!fn(value)) throw Error(`${kind} schema: ${fn.errors.map(e=>`${e.instancePath||'/'} ${e.message} ${JSON.stringify(e.params)}`).join('; ')}`);
}
export function coreIdentity() {
 const files=['runtime.mjs','config.mjs','guidance.mjs','migration.mjs','validators.cjs','build-validators.mjs','../sync-guidance.mjs','../WORKFLOW.md','../DECISIONS.md',...names.map(n=>'schemas/'+n)];
 return hash(JSON.stringify(files.map(n=>[n,readFileSync(new URL(n,home),'utf8')])));
}
export function safePath(root,name,{missing=false}={}) {
 if(typeof name!=='string'||!name||isAbsolute(name)||name.includes('\\')||name.split('/').some(p=>p==='..'||p==='.'||!p)||/^[A-Za-z]:/.test(name)) throw Error('Unsafe repository path: '+name);
 const target=resolve(root,name);
 if(relative(root,target).startsWith('..'+sep)) throw Error('Path escapes repository: '+name);
 let p=root;
 for(const part of name.split('/')) {
  p=resolve(p,part);let stat;try{stat=lstatSync(p);}catch(e){if(e.code!=='ENOENT')throw e;}
  if(stat?.isSymbolicLink())throw Error('Symlink requires explicit handling: '+name);
  if(!stat&&!missing)throw Error('Missing file: '+name);
 }
 if(existsSync(target)&&!lstatSync(target).isFile())throw Error('Expected regular file: '+name);
 return target;
}
export const historical = p => /^(docs\/(history|archive|baseline)\/|artifacts\/)/.test(p);
export const boundary = 'Only this operation/checkpoint is blocked. Continue investigation or independent authorized work; resolve unclear authority before dependent implementation.';
