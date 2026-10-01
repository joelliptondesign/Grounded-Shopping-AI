import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, relative } from 'node:path';
import { validate, safePath, hash } from './runtime.mjs';
const plain = s => s.replace(/[\\`*_{}\[\]()#!|~]/g,'\\$&');
export function syncGuidance(root,mapName,{write=false,historicalPrefixes=['docs/history/','docs/archive/','docs/baseline/','artifacts/']}={}) {
 const historical=p=>historicalPrefixes.some(prefix=>p.startsWith(prefix));
 if(!mapName)return {changed:[],dependencies:[],fingerprint:hash('disabled')};
 const mapFile=safePath(root,mapName), mapText=readFileSync(mapFile,'utf8');
 const map=JSON.parse(mapText);validate('guidanceMap',map);
 const seen=new Set(),records=new Set(map.topics.map(t=>t.record)),sources=[[mapName,mapText]],destinations=new Map();
 for(const topic of map.topics) {
  if(seen.has(topic.key))throw Error('Duplicate guidance topic: '+topic.key);seen.add(topic.key);
  if(historical(topic.record))throw Error('Historical guidance source: '+topic.record);
  const source=readFileSync(safePath(root,topic.record),'utf8');sources.push([topic.record,source]);
  const start='<!-- groundwork:decision-summary:start -->',end='<!-- groundwork:decision-summary:end -->';
  if(source.split(start).length!==2||source.split(end).length!==2||source.indexOf(start)>source.indexOf(end))throw Error('Invalid decision-summary markers: '+topic.record);
  const content=source.slice(source.indexOf(start)+start.length,source.indexOf(end)).trim();
  const match=/^```json\r?\n([\s\S]*?)\r?\n```$/.exec(content);
  if(!match)throw Error('Expected one JSON decision-summary block: '+topic.record);
  const data=JSON.parse(match[1]);validate('decision',data);
  if(!topic.record.split('/').pop().startsWith(data.id+'-'))throw Error('Decision ID does not match filename: '+topic.record);
  if(data.status!=='accepted'||data.supersededBy)throw Error('Active topic requires an accepted, nonsuperseded decision: '+topic.key);
  for(const target of topic.targets) {
   if(historical(target)||records.has(target))throw Error('Invalid guidance destination: '+target);
   if(!destinations.has(target))destinations.set(target,{path:safePath(root,target),original:readFileSync(safePath(root,target),'utf8'),sections:new Map()});
   const link=relative(dirname(target),topic.record).split('/').map(encodeURIComponent).join('/');
   destinations.get(target).sections.set(topic.key,`**${plain(data.title)}** · Accepted\n\n${data.summary.map(s=>'- '+plain(s)).join('\n')}\n\n**Why:** ${plain(data.rationale)}\n\n[Full decision: ${data.id}](${link})`);
  }
 }
 const plan=[];
 for(const [name,dest] of destinations) {
  const token=/<!-- groundwork:generated:([a-z][a-z0-9-]*):(start|end) -->/g;
  const matches=[...dest.original.matchAll(token)];
  if((dest.original.match(/<!-- groundwork:generated:/g)||[]).length!==matches.length)throw Error('Malformed guidance marker: '+name);
  const found=new Set();let next='',cursor=0;
  if(matches.length!==dest.sections.size*2)throw Error('Missing, duplicate or orphan guidance markers: '+name);
  for(let i=0;i<matches.length;i+=2){const a=matches[i],b=matches[i+1];
   if(a[2]!=='start'||b?.[2]!=='end'||a[1]!==b[1]||found.has(a[1])||!dest.sections.has(a[1]))throw Error('Nested, reversed or orphan guidance markers: '+name);
   found.add(a[1]);next+=dest.original.slice(cursor,a.index+a[0].length)+'\n'+dest.sections.get(a[1])+'\n';cursor=b.index;
  }
  next+=dest.original.slice(cursor);
  if(next!==dest.original)plan.push({name,...dest,next});
 }
 if(!write&&plan.length)throw Error('Stale generated guidance: '+plan.map(p=>p.name).join(', ')+'. Read authoritative records, then run node scripts/sync-guidance.mjs --write to repair.');
 // Recheck authoritative inputs before writing any destination.
 for(const [name,original] of sources) if(readFileSync(safePath(root,name),'utf8')!==original)throw Error('Guidance source changed during generation: '+name);
 const changed=[];
 try{for(const p of plan){safePath(root,p.name);if(readFileSync(p.path,'utf8')!==p.original)throw Error('Destination changed during generation: '+p.name);writeFileSync(p.path,p.next);changed.push(p.name);}}
 catch(e){throw Error(e.message+'; files already written: '+(changed.join(', ')||'none'));}
 return {changed,dependencies:[...new Set(sources.map(([n])=>n))],fingerprint:hash(JSON.stringify(sources.sort(([a],[b])=>a.localeCompare(b))))};
}
