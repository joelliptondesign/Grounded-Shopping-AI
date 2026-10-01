import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync, rmSync } from 'node:fs';
import { dirname } from 'node:path';
import { execFileSync } from 'node:child_process';
import { validate, safePath, hash } from './runtime.mjs';
export function migrate(root,name) {
 const path=safePath(root,name),before=readFileSync(path,'utf8'),old=JSON.parse(before);
 if(old.version===3){validate('receiptV3',old);return 'Receipt already v3; unchanged.';}
 if(old.version!==2)throw Error('Unsupported receipt version; migration accepts only known v2 receipts. Original preserved.');
 validate('receiptV2',old);
 execFileSync('git',['rev-parse','--verify',old.base+'^{commit}'],{cwd:root,stdio:'pipe'});
 const result=structuredClone(old);result.version=3;
 result.decisionImpact??={status:'pending',disposition:null,reason:'',reviewer:'',records:[],fingerprint:null};
 for(const a of [...result.groups,result.projectContext,result.decisionImpact]){a.status='pending';a.fingerprint=null;}
 validate('receiptV3',result);
 const backupName='docs/history/groundwork-migrations/'+hash(before)+'.json';
 const backup=safePath(root,backupName,{missing:true});mkdirSync(dirname(backup),{recursive:true});
 if(existsSync(backup)){if(readFileSync(backup,'utf8')!==before)throw Error('Migration backup conflict');}else writeFileSync(backup,before,{flag:'wx'});
 const temp=safePath(root,name+'.migration-'+process.pid+'.tmp',{missing:true});
 try {
  writeFileSync(temp,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  safePath(root,name);if(readFileSync(path,'utf8')!==before)throw Error('Receipt changed during migration; current receipt preserved');
  renameSync(temp,path);
 }finally{if(existsSync(temp))rmSync(temp);}
 return `Migrated v2 to v3; assessments pending. Original: ${backupName}. Run --draft --base ${old.base}, then review.`;
}
