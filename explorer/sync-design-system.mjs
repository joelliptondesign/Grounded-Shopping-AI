// Generated copies consume the Joel Knowledge Explorer's authoritative design files.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const target=path.join(import.meta.dirname,'design-system');
const files=['workflow-tokens.css','explorer-components.css','source-view.css'];
const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
export async function verifyDesignSystem(){
 const manifest=JSON.parse(await fs.readFile(path.join(target,'provenance.json'),'utf8'));
 for(const name of files)if(hash(await fs.readFile(path.join(target,name),'utf8'))!==manifest.hashes[name])throw Error('Generated design file changed: '+name+'. Edit the canonical Explorer and sync deliberately.');
}
if(process.argv[1]===import.meta.filename){
 if(process.argv[2]==='--check'){await verifyDesignSystem();console.log('Explorer design copies match their recorded source hashes.');}
 else {
  const source=process.argv[2];if(!source)throw Error('Pass the canonical Architecture Explorer output directory, or --check.');
  const content=await Promise.all(files.map(name=>fs.readFile(path.join(source,name),'utf8')));
  await fs.mkdir(target,{recursive:true});for(let i=0;i<files.length;i++)await fs.writeFile(path.join(target,files[i]),content[i]);
  await fs.writeFile(path.join(target,'provenance.json'),JSON.stringify({owner:'Joel Knowledge Architecture Explorer',source:path.resolve(source),hashes:Object.fromEntries(files.map((name,i)=>[name,hash(content[i])]))},null,2)+'\n');
  await verifyDesignSystem();console.log('Synced canonical Explorer tokens and components.');
 }
}
