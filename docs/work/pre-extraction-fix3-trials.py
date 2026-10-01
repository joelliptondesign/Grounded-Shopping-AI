from pathlib import Path
import tempfile,shutil,subprocess,json,time,hashlib,statistics
src=Path('/Users/joellipton/Desktop/Grounded-Shopping-AI'); root=Path(tempfile.mkdtemp(prefix='groundwork-fix3-')); baseline=root/'baseline';baseline.mkdir();results=[]
for name in ['AGENTS.md','CLAUDE.md','GOVERNANCE.md','README.md','docs','scripts/check-docs.mjs','scripts/sync-guidance.mjs','scripts/groundwork','frontend/README.md','frontend/CLAUDE.md','api/README.md']:
 p=src/name;q=baseline/name;q.parent.mkdir(parents=True,exist_ok=True)
 if p.is_dir():shutil.copytree(p,q,ignore=shutil.ignore_patterns('history','archive','baseline','node_modules'))
 else:shutil.copy2(p,q)
(baseline/'docs/documentation-review.json').unlink()
def git(p,*args):return subprocess.check_output(['git',*args],cwd=p,text=True).strip()
git(baseline,'init','-q');git(baseline,'add','.');git(baseline,'-c','user.name=Trial','-c','user.email=trial@localhost','commit','-qm','Working-source fixture')
base=git(baseline,'rev-parse','HEAD')
def start(name):
 p=root/name;shutil.copytree(baseline,p);row={'scenario':name,'checks':[]};results.append(row);return p,row
def run(p,row,args,expect=0,preload=None):
 cmd=['node']+(['--import',str(preload)] if preload else [])+args;t=time.perf_counter();r=subprocess.run(cmd,cwd=p,text=True,capture_output=True);row['checks'].append({'args':args,'exit':r.returncode,'milliseconds':round((time.perf_counter()-t)*1000,2),'output':(r.stdout+r.stderr).strip()});assert (r.returncode==0)==(expect==0),row['checks'][-1];return r
adr='docs/decisions/DR-0001-scrolling-conflict.md'
def metadata(p,patch):
 q=p/adr;s=q.read_text();a=s.index('```json\n')+8;b=s.index('\n```',a);d=json.loads(s[a:b]);d.update(patch);q.write_text(s[:a]+json.dumps(d,indent=2)+s[b:])
def complete(p,row,disposition='none',records=[]):
 run(p,row,['scripts/check-docs.mjs','--draft']);q=p/'docs/documentation-review.json';r=json.loads(q.read_text());r['decisionImpact'].update(disposition=disposition,records=records);q.write_text(json.dumps(r))
 if records:run(p,row,['scripts/check-docs.mjs','--draft']);r=json.loads(q.read_text())
 for g in r['groups']:g.update(status='reviewed',disposition='updated' if all(git(p,'diff','--name-only','HEAD','--',d) for d in g['documents']) else 'no-impact',reviewer='Codex isolated trial',reason='Trial changes preserve application behavior; affected guidance and its generated summaries were reviewed against the fixture diff.')
 r['projectContext'].update(status='reviewed',changed=False,reviewer='Codex isolated trial',reason='Fixture exercises review mechanics without changing actual project capabilities or production state.')
 r['decisionImpact'].update(status='reviewed',reviewer='Codex isolated trial',reason='Trial follows the stated record disposition and preserves actual project decisions; synthetic approvals are fixture data only.')
 q.write_text(json.dumps(r,indent=2)+'\n');run(p,row,['scripts/check-docs.mjs'])
# 1 lifecycle
p,row=start('rationale-update-review');metadata(p,{'rationale':'Keep the beginning visible so a reader can follow the answer naturally.'});run(p,row,['scripts/check-docs.mjs'],1);run(p,row,['scripts/sync-guidance.mjs','--write']);complete(p,row,'update',[adr]);receipt=(p/'docs/documentation-review.json').read_bytes();run(p,row,['scripts/sync-guidance.mjs','--write']);run(p,row,['scripts/check-docs.mjs','--draft']);assert (p/'docs/documentation-review.json').read_bytes()==receipt
# 2 explicit supersession, no auto-selection of new proposal
p,row=start('explicit-successor');new='docs/decisions/DR-0005-trial-successor.md';s=(p/adr).read_text().replace('DR-0001','DR-0005').replace('"status": "accepted"','"status": "proposed"');(p/new).write_text(s);run(p,row,['scripts/sync-guidance.mjs','--check']);m=json.loads((p/'docs/guidance-map.json').read_text());m['topics'][0]['record']=new;(p/'docs/guidance-map.json').write_text(json.dumps(m));run(p,row,['scripts/sync-guidance.mjs','--write'],1);metadata(p,{'status':'superseded','supersededBy':new});(p/new).write_text(s.replace('"status": "proposed"','"status": "accepted"'));run(p,row,['scripts/sync-guidance.mjs','--write']);assert 'DR-0005' in (p/'CLAUDE.md').read_text();assert '"status": "superseded"' in (p/adr).read_text();complete(p,row,'create',[new,adr])
# 3 incomplete metadata does not lock the workspace
p,row=start('missing-rationale-repair');metadata(p,{'rationale':''});bad=(p/'CLAUDE.md').read_bytes();r=run(p,row,['scripts/sync-guidance.mjs','--write'],1);assert 'independent authorized work' in r.stderr;assert (p/'CLAUDE.md').read_bytes()==bad;(p/'docs/work/independent-note.md').write_text('Independent investigation remained possible.\n');metadata(p,{'rationale':'Preserve the reading position while the response unfolds.'});run(p,row,['scripts/sync-guidance.mjs','--write']);complete(p,row,'update',[adr])
# 4 both migration shapes, complete current lifecycle
for variant in ['shopping','portfolio']:
 p,row=start('migration-'+variant);(p/'docs/work/trial.md').write_text('Routine fixture note.\n');complete(p,row);q=p/'docs/documentation-review.json';r=json.loads(q.read_text());r['version']=2
 if variant=='portfolio':del r['decisionImpact']
 q.write_text(json.dumps(r));original=q.read_bytes();run(p,row,['scripts/check-docs.mjs'],1);run(p,row,['scripts/check-docs.mjs','--migrate']);backup=p/'docs/history/groundwork-migrations'/ (hashlib.sha256(original).hexdigest()+'.json');assert backup.read_bytes()==original;run(p,row,['scripts/check-docs.mjs'],1);complete(p,row);run(p,row,['scripts/check-docs.mjs','--migrate'])
# 5 deterministic filesystem fault in a disposable copy
p,row=start('partial-write-recovery');metadata(p,{'rationale':'A synthetic changed rationale for fault recovery.'});hook=root/'write-fault.mjs';hook.write_text("import fs from 'node:fs';import {syncBuiltinESMExports} from 'node:module';const original=fs.writeFileSync;fs.writeFileSync=function(p,...args){if(String(p).endsWith('/CLAUDE.md'))throw Error('Injected write failure');return original.call(this,p,...args)};syncBuiltinESMExports();")
r=run(p,row,['scripts/sync-guidance.mjs','--write'],1,hook);assert 'files already written: AGENTS.md' in r.stderr;run(p,row,['scripts/sync-guidance.mjs','--check'],1);run(p,row,['scripts/sync-guidance.mjs','--write']);complete(p,row,'update',[adr])
# 6 concurrent receipt edit detected before replacement
p,row=start('migration-concurrent-edit');(p/'docs/work/trial.md').write_text('Routine note.');complete(p,row);q=p/'docs/documentation-review.json';r=json.loads(q.read_text());r['version']=2;q.write_text(json.dumps(r));before=q.read_bytes();hook=root/'migration-fault.mjs';hook.write_text("import fs from 'node:fs';import{syncBuiltinESMExports}from'node:module';const orig=fs.writeFileSync;fs.writeFileSync=function(p,...args){const v=orig.call(this,p,...args);if(String(p).includes('.migration-'))orig.call(this,'docs/documentation-review.json','concurrent writer content');return v};syncBuiltinESMExports();")
r=run(p,row,['scripts/check-docs.mjs','--migrate'],1,hook);assert 'changed during migration' in r.stderr;assert q.read_text()=='concurrent writer content';assert (p/'docs/history/groundwork-migrations'/(hashlib.sha256(before).hexdigest()+'.json')).read_bytes()==before;q.write_bytes(before);run(p,row,['scripts/check-docs.mjs','--migrate']);complete(p,row)
# 7 multi-topic same destination
p,row=start('multiple-topics');new='docs/decisions/DR-0005-trial-second-topic.md';(p/new).write_text((p/adr).read_text().replace('DR-0001','DR-0005'));m=json.loads((p/'docs/guidance-map.json').read_text());m['topics'].append({'key':'second-topic','record':new,'targets':['AGENTS.md']});(p/'docs/guidance-map.json').write_text(json.dumps(m));q=p/'AGENTS.md';q.write_text(q.read_text()+'\n<!-- groundwork:generated:second-topic:start -->\n<!-- groundwork:generated:second-topic:end -->\n');run(p,row,['scripts/sync-guidance.mjs','--write']);assert 'Full decision: DR-0001' in q.read_text() and 'Full decision: DR-0005' in q.read_text();complete(p,row,'create',[new])
times=[c['milliseconds'] for row in results for c in row['checks']];data={'source_head':git(src,'rev-parse','HEAD'),'source_modules':{str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (src/'scripts/groundwork').glob('*.mjs')},'scope':'Isolated current-guidance copies with temporary Git baselines. V2 shape fixtures use the temporary base, not original product commits. No real decision superseded. Faults injected only in disposable copies.','temporary_root':str(root),'scenarios':results,'commands':len(times),'milliseconds':{'min':min(times),'median':statistics.median(times),'max':max(times)}}
Path('/tmp/fix3-results.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'scenarios':len(results),'commands':len(times),'timings':data['milliseconds'],'all_expected_results':True},indent=2))
