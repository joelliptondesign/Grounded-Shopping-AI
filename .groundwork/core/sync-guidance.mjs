import { loadConfig } from './groundwork/config.mjs';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { syncGuidance } from './groundwork/guidance.mjs';
import { boundary } from './groundwork/runtime.mjs';
try {
 const args=process.argv.slice(2);let configName;const at=args.indexOf('--config');if(at>=0){if(!args[at+1])throw Error('--config requires a path');configName=args[at+1];args.splice(at,2);}if(args.length!==1||!['--write','--check'].includes(args[0]))throw Error('Usage: node scripts/sync-guidance.mjs --check | --write');
 const root=execFileSync('git',['rev-parse','--show-toplevel'],{encoding:'utf8'}).trim();
 const config=loadConfig(root,configName);
 const map=JSON.parse(readFileSync(root+'/'+config.mapPath,'utf8'));
 const r=syncGuidance(root,config.guidanceMap ?? map.guidanceMap,{write:args[0]==='--write',historicalPrefixes:config.historicalPrefixes});
 console.log(r.changed.length?'Updated guidance: '+r.changed.join(', '):'Generated guidance current; no files changed.');
}catch(e){console.error(e.message+'\n'+boundary);process.exitCode=1;}
