import { existsSync, readFileSync } from 'node:fs';
import { safePath, validate } from './runtime.mjs';
export const defaults = {
 version:1,receiptPath:'docs/documentation-review.json',contextPath:'docs/PROJECT-STATE.md',mapPath:'docs/documentation-map.json',
 decisionsDirectory:'docs/decisions',migrationBackupDirectory:'docs/history/groundwork-migrations',
 decisionGuidance:['AGENTS.md','docs/workflow/README.md','docs/decisions/README.md','docs/decisions/TEMPLATE.md'],
 historicalPrefixes:['docs/history/','docs/archive/','docs/baseline/','artifacts/'],guidanceMap:null
};
export function loadConfig(root,name) {
 const file=name ?? '.groundwork/config.json';safePath(root,file,{missing:!name});
 const raw=existsSync(root+'/'+file)?JSON.parse(readFileSync(root+'/'+file,'utf8')):{version:1};validate('config',raw);
 const config={...defaults,...raw};
 for(const key of ['receiptPath','contextPath','mapPath'])safePath(root,config[key],{missing:true});
 if(new Set([config.receiptPath,config.contextPath,config.mapPath]).size!==3)throw Error('Configuration paths must be distinct');
 if(config.guidanceMap)safePath(root,config.guidanceMap,{missing:true});
 for(const path of config.decisionGuidance)safePath(root,path,{missing:true});
 for(const key of ['decisionsDirectory','migrationBackupDirectory'])safePath(root,config[key]+'/__groundwork_probe__',{missing:true});
 for(const prefix of config.historicalPrefixes){if(!prefix.endsWith('/'))throw Error('Historical prefixes must end with /');safePath(root,prefix+'__groundwork_probe__',{missing:true});}
 if(!config.historicalPrefixes.some(p=>config.migrationBackupDirectory.startsWith(p)))throw Error('Migration backups must be under a configured historical prefix');
 return config;
}
