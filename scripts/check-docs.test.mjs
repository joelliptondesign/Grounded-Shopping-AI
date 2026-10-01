import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, copyFileSync, cpSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
const checker = resolve('.groundwork/core/check-docs.mjs');
function fixture(t) {
  const cwd = mkdtempSync(join(tmpdir(), 'doc-impact-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const write = (p, value) => writeFileSync(join(cwd, p), value);
  const read = p => readFileSync(join(cwd, p), 'utf8');
  const git = (...args) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
  for (const p of ['docs','src','tests','docs/decisions']) mkdirSync(join(cwd, p));
  copyFileSync(checker, join(cwd, 'check.mjs'));
  for(const name of ['WORKFLOW.md','DECISIONS.md','sync-guidance.mjs'])copyFileSync(resolve('.groundwork/core',name),join(cwd,name));
  cpSync(resolve('.groundwork/core/groundwork'),join(cwd,'groundwork'),{recursive:true,filter:p=>!p.includes('node_modules')});
  for (const p of ['docs/experience.md','docs/architecture.md','docs/PROJECT-STATE.md','README.md']) write(p, 'Current description\n');
  write('src/app.js','original'); write('tests/app.js','test');
  write('docs/decisions/DR-0001-original.md', '# Original decision\nStatus: Accepted\nDecider: Fixture owner\n');
  const map = { rules: [
    { id: 'app', prefixes: ['src/'], docs: ['docs/experience.md','docs/architecture.md'] },
    { id: 'tests', prefixes: ['tests/'], docs: ['README.md'] },
    { id: 'docs', prefixes: ['docs/','README.md'], docs: [] },
    { id: 'tool', prefixes: ['check.mjs','groundwork/','sync-guidance.mjs','WORKFLOW.md','DECISIONS.md','.groundwork/'], docs: [] },
  ] };
  write('docs/documentation-map.json', JSON.stringify(map));
  git('init','-q'); git('add','.');
  const commit = () => git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture');
  commit(); const base = git('rev-parse','HEAD');
  const run = (...args) => spawnSync(process.execPath, ['check.mjs', ...args], { cwd, encoding: 'utf8' });
  const pass = (...args) => { const r = run(...args); assert.equal(r.status,0,r.stderr); return r; };
  const receipt = () => JSON.parse(read('docs/documentation-review.json'));
  const save = r => write('docs/documentation-review.json', JSON.stringify(r));
  const approve = () => { const r = receipt(); for (const g of r.groups) Object.assign(g,{status:'reviewed',disposition:'no-impact',reason:'Implementation changes preserve the documented behavior.',reviewer:'Test agent'}); Object.assign(r.projectContext,{status:'reviewed',changed:false,reason:'No summarized capability, constraint, gap or status changed.',reviewer:'Test agent'}); Object.assign(r.decisionImpact,{status:'reviewed',disposition:'none',reason:'Routine implementation preserves all existing decisions.',reviewer:'Test agent',records:[]}); save(r); };
  const ready = () => { pass('--draft'); approve(); pass(); };
  return { cwd, write, read, git, commit, base, run, pass, receipt, save, approve, ready, map };
}
test('clean tree; untracked changes need review; draft never approves', t => {
  const f=fixture(t); f.pass(); f.write('src/new.js','new'); assert.match(f.run().stderr,/review missing/);
  f.pass('--draft'); assert.match(f.run().stderr,/Pending group/); f.approve(); f.pass();
});
test('source edits invalidate relevant groups; redraft keeps stale groups pending', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.write('src/app.js','next');
  assert.match(f.run().stderr,/Stale group/); f.pass('--draft'); assert.ok(f.receipt().groups.every(g=>g.status==='pending')); assert.notEqual(f.run().status,0);
});
test('unrelated source area preserves reviewed groups and adds new coverage', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const before=f.receipt().groups;
  f.write('tests/app.js','next'); assert.match(f.run().stderr,/Missing coverage: README/); f.pass('--draft');
  assert.deepEqual(f.receipt().groups.slice(0,2),before); assert.equal(f.receipt().groups[2].status,'pending');
  assert.equal(f.receipt().projectContext.status,'pending'); f.approve(); f.pass();
});
test('unrelated evidence does not invalidate completed doc groups', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const before=f.receipt().groups;
  f.write('docs/result.md','Test evidence'); f.pass('--draft'); assert.deepEqual(f.receipt().groups,before);
  f.approve(); f.pass();
});
test('group several docs under one explanation; draft binds the union', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.pass('--draft'); const r=f.receipt();
  r.groups=[{...r.groups[0],documents:['docs/experience.md','docs/architecture.md']}]; f.save(r);
  f.pass('--draft'); assert.equal(f.receipt().groups.length,1); assert.equal(f.receipt().groups[0].status,'pending'); f.approve(); f.pass();
});
test('editing reviewed documentation invalidates only that group', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.write('docs/experience.md','Updated description'); f.pass('--draft');
  const groups=f.receipt().groups; assert.equal(groups.find(g=>g.documents.includes('docs/experience.md')).status,'pending'); assert.equal(groups.find(g=>g.documents.includes('docs/architecture.md')).status,'reviewed');
});
test('relevant rule changes invalidate affected groups; unrelated rule does not', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.map.rules[1].prefixes.push('spec/'); f.write('docs/documentation-map.json',JSON.stringify(f.map)); f.pass('--draft'); assert.ok(f.receipt().groups.every(g=>g.status==='reviewed'));
  f.map.rules[0].prefixes.push('lib/'); f.write('docs/documentation-map.json',JSON.stringify(f.map)); f.pass('--draft'); assert.ok(f.receipt().groups.every(g=>g.status==='pending'));
});
test('updated disposition needs actual doc diff', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const r=f.receipt(); r.groups[0].disposition='updated'; f.save(r); assert.match(f.run().stderr,/unchanged/);
});
test('Project Context assessment is required even with no mapped docs', t => {
  const f=fixture(t); f.write('docs/note.md','note'); f.pass('--draft'); assert.equal(f.receipt().groups.length,0); assert.match(f.run().stderr,/Project Context assessment/); f.approve(); f.pass();
  const r=f.receipt(); r.projectContext.changed=true; f.save(r); assert.match(f.run().stderr,/has no diff/);
  f.write('docs/PROJECT-STATE.md','New capability'); f.pass('--draft'); f.approve(); const n=f.receipt(); n.projectContext.changed=true; f.save(n); f.pass();
});
test('new source file in already reviewed area makes its group stale', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.write('src/new.js','new'); assert.match(f.run().stderr,/Stale group/);
});
test('unmapped paths and deleted docs fail', t => {
  const f=fixture(t); f.write('unknown.txt','new'); assert.match(f.run().stderr,/Unmapped/); rmSync(join(f.cwd,'unknown.txt'));
  f.git('rm','docs/experience.md'); assert.match(f.run().stderr,/Mapped document missing/);
});
test('rename and deletion included; review survives commit with explicit base', t => {
  const f=fixture(t); f.git('mv','src/app.js','src/renamed.js'); const report=JSON.parse(f.pass('--report').stdout); assert.deepEqual(report.changed,['src/app.js','src/renamed.js']);
  f.ready(); f.git('add','.'); f.commit(); f.pass('--base',f.base); f.write('src/renamed.js','later'); assert.match(f.run().stderr,/another base/);
});
test('missing coverage, duplicate docs, and unrelated evidence fail', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const good=f.receipt();
  f.save({...good,groups:[]}); assert.match(f.run().stderr,/Missing coverage/);
  f.save({...good,groups:[...good.groups,good.groups[0]]}); assert.match(f.run().stderr,/Duplicate review/);
  const bad=structuredClone(good); bad.groups[0].evidence=['unknown.js']; f.save(bad); assert.match(f.run().stderr,/Evidence must/);
});
test('unknown legacy receipt is preserved and never silently drafted', t => {
 const f=fixture(t);f.write('src/app.js','change');f.save({base:f.base,entries:[]});const before=f.read('docs/documentation-review.json');
 assert.match(f.run().stderr,/format v3/);assert.notEqual(f.run('--draft').status,0);assert.notEqual(f.run('--migrate').status,0);assert.equal(f.read('docs/documentation-review.json'),before);
});
test('extra semantic target is allowed and bound to its cited evidence', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.write('docs/extra.md','Additional contract'); f.pass('--draft'); const r=f.receipt(); r.groups.push({...r.groups[0],documents:['docs/extra.md'],evidence:['src/app.js'],status:'pending'}); f.save(r); f.pass('--draft'); f.approve(); f.pass();
  f.write('docs/extra.md','revised'); assert.match(f.run().stderr,/Stale group: docs\/extra/);
});
test('redraft is idempotent for completed review; reverted area drops obsolete groups', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const prior=f.receipt(); f.pass('--draft'); assert.deepEqual(f.receipt(),prior);
  f.write('src/app.js','original'); f.write('docs/note.md','note'); f.pass('--draft'); assert.equal(f.receipt().groups.length,0); f.approve(); f.pass();
});
test('changing the checker invalidates all groups', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.write('check.mjs',f.read('check.mjs')+'\n// checker revision\n'); f.pass('--draft'); assert.ok(f.receipt().groups.every(g=>g.status==='pending'));
});
test('context edit reopens context assessment without reopening unrelated groups', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const before=f.receipt().groups;
  f.write('docs/PROJECT-STATE.md','Revised project summary'); f.pass('--draft'); assert.deepEqual(f.receipt().groups,before); assert.equal(f.receipt().projectContext.status,'pending');
});
test('grouping two docs binds both and rejects partially updated claims', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.pass('--draft'); const r=f.receipt(); r.groups=[{...r.groups[0],documents:['docs/experience.md','docs/architecture.md']}]; f.save(r); f.pass('--draft'); f.approve(); f.pass();
  f.write('docs/experience.md','Changed description'); f.pass('--draft'); assert.equal(f.receipt().groups[0].status,'pending'); f.approve(); const n=f.receipt(); n.groups[0].disposition='updated'; f.save(n); assert.match(f.run().stderr,/unchanged: docs\/architecture/);
});
test('new change base starts fresh groups instead of inheriting the last task', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); f.git('add','.'); f.commit();
  f.write('tests/app.js','new task'); f.pass('--draft');
  assert.deepEqual(f.receipt().groups.map(g=>g.documents),[['README.md']]);
  assert.equal(f.receipt().groups[0].status,'pending'); f.approve(); f.pass();
});
test('untracked root Word documents are reported but not read; tracking removes exemption', t => {
  const f=fixture(t); f.map.untrackedNonSiteExtensions=['.docx']; f.write('docs/documentation-map.json',JSON.stringify(f.map));
  f.write('resume.docx','non-site content'); const report=JSON.parse(f.pass('--report').stdout);
  assert.deepEqual(report.excludedUntracked,['resume.docx']); assert.ok(!report.changed.includes('resume.docx'));
  f.git('add','resume.docx'); assert.match(f.run('--report').stderr,/Unmapped changed file: resume/);
});
test('working review cannot be mistaken for staged-content verification', t => {
  const f=fixture(t); assert.match(f.run('--staged').stderr,/not the staged index/);
  f.write('src/app.js','staged version'); f.git('add','src/app.js'); f.ready();
  f.write('src/app.js','unstaged version'); assert.match(f.run().stderr,/Stale group/);
});
test('large changed media is fully hashed; same-length byte change invalidates review', t => {
  const f=fixture(t); mkdirSync(join(f.cwd,'assets')); f.map.rules.push({id:'media',prefixes:['assets/'],docs:['docs/experience.md']});
  f.write('docs/documentation-map.json',JSON.stringify(f.map)); const bytes=Buffer.alloc(20*1024*1024,1); f.write('assets/demo.mp4',bytes); f.ready();
  bytes[bytes.length-1]=2; f.write('assets/demo.mp4',bytes); assert.match(f.run().stderr,/Stale group/);
});
test('historical documentation is excluded from ordinary review targets', t => {
  const f=fixture(t); mkdirSync(join(f.cwd,'docs/history')); f.write('docs/history/past.md','Historical observation');
  f.map.rules[2].prefixes=['README.md','docs/PROJECT-STATE.md','docs/documentation-map.json'];
  f.map.rules.push({id:'history',prefixes:['docs/history/'],docs:[],historical:true}); f.write('docs/documentation-map.json',JSON.stringify(f.map));
  f.pass('--draft'); f.approve(); f.pass(); const r=f.receipt();r.groups.push({documents:['docs/history/past.md'],evidence:['docs/documentation-map.json']});f.save(r);assert.match(f.run().stderr,/nonhistorical Markdown|schema/);
});

test('shopping routing keeps frontend, engine, eval and harness reviews separate', () => {
 const map=JSON.parse(readFileSync('docs/documentation-map.json','utf8'));
 const targets=p=>[...new Set(map.rules.filter(r=>r.prefixes.some(x=>p.startsWith(x))).flatMap(r=>r.docs))].sort();
 for(const [p,want] of [
 ['frontend/Rufus Shopping Agent.dc.html',['frontend/README.md']],
 ['engine/decision.py',['GOVERNANCE.md','docs/ARCHITECTURE.md']],
 ['evals/runner.py',['docs/EVALUATION.md']],
 ['scripts/verify-offline.py',['docs/workflow/README.md']],
 ['artifacts/evals/core/run.json',[]]
 ])assert.deepEqual(targets(p),want.sort());
});
test('historical evaluation reports cannot become review targets',t=>{
 const f=fixture(t);mkdirSync(join(f.cwd,'artifacts'));f.write('artifacts/run.md','Old report');
 f.map.rules.push({id:'history',prefixes:['artifacts/'],docs:[],historical:true});f.write('docs/documentation-map.json',JSON.stringify(f.map));
 f.write('src/app.js','change');f.ready();const r=f.receipt();r.groups.push({documents:['artifacts/run.md'],evidence:['src/app.js']});f.save(r);
 assert.match(f.run().stderr,/nonhistorical Markdown|schema/);
});

// Decision assessment extends the same checkpoint, without approving ADRs.
function assessDecision(f, disposition, records = []) {
  f.pass('--draft');
  const draft=f.receipt(); Object.assign(draft.decisionImpact,{disposition,records}); f.save(draft);
  f.pass('--draft'); f.approve();
  const reviewed=f.receipt(); Object.assign(reviewed.decisionImpact,{disposition,records}); f.save(reviewed);
}
test('v3 missing decision assessment fails; v2 migration explicitly adds it pending', t => {
 const f=fixture(t);f.write('src/app.js','change');f.ready();const r=f.receipt();delete r.decisionImpact;f.save(r);
 assert.match(f.run().stderr,/schema/);assert.notEqual(f.run('--draft').status,0);
 r.version=2;f.save(r);f.pass('--migrate');assert.equal(f.receipt().decisionImpact.status,'pending');assert.equal(f.receipt().decisionImpact.disposition,null);
 f.pass('--draft');f.approve();f.pass();
});
test('none needs rationale and reviewer, and cannot link records', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const good=f.receipt();
  for (const patch of [{reason:''},{reviewer:''},{disposition:'skip'},{status:'pending'}]) {
    const r=structuredClone(good); Object.assign(r.decisionImpact,patch); f.save(r);
    assert.match(f.run().stderr,/Decision impact assessment missing|schema/);
  }
  f.save(good); assessDecision(f,'none',['docs/decisions/DR-0001-original.md']);
  assert.match(f.run().stderr,/none must not link/);
});
test('existing record passes unchanged and cannot claim new or modified records', t => {
  const f=fixture(t); f.write('src/app.js','change');
  assessDecision(f,'existing',['docs/decisions/DR-0001-original.md']); f.pass();
  f.write('docs/decisions/DR-0001-original.md','Revised choice');
  assessDecision(f,'existing',['docs/decisions/DR-0001-original.md']);
  assert.match(f.run().stderr,/requires unchanged records/);
  f.write('docs/decisions/DR-0002-new.md','New choice');
  assessDecision(f,'existing',['docs/decisions/DR-0002-new.md']);
  assert.match(f.run().stderr,/requires unchanged records/);
});
test('update and create must match actual record changes', t => {
  const f=fixture(t); f.write('src/app.js','change');
  assessDecision(f,'update',['docs/decisions/DR-0001-original.md']);
  assert.match(f.run().stderr,/requires a changed existing record/);
  f.write('docs/decisions/DR-0001-original.md','Clarified accepted choice');
  assessDecision(f,'update',['docs/decisions/DR-0001-original.md']); f.pass();
  assessDecision(f,'create',['docs/decisions/DR-0001-original.md']);
  assert.match(f.run().stderr,/requires a new record/);
  f.write('docs/decisions/DR-0002-new.md','New choice');
  assessDecision(f,'update',['docs/decisions/DR-0002-new.md']);
  assert.match(f.run().stderr,/requires a changed existing record/);
  assessDecision(f,'create',['docs/decisions/DR-0002-new.md','docs/decisions/DR-0001-original.md']); f.pass();
});
test('record links reject missing, duplicate, non-record and unsafe paths', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const good=f.receipt();
  for (const records of [null,[],['docs/decisions/DR-9999-missing.md'],['README.md'],['../outside.md'],['docs/decisions/DR-0001-original.md','docs/decisions/DR-0001-original.md']]) {
    const r=structuredClone(good); Object.assign(r.decisionImpact,{disposition:'existing',records}); f.save(r);
    assert.notEqual(f.run().status,0);
  }
});
test('source edits reopen decision assessment; unrelated doc groups stay reviewed', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const before=f.receipt().groups;
  f.write('tests/app.js','new change'); assert.match(f.run().stderr,/Decision impact assessment stale/);
  f.pass('--draft'); assert.equal(f.receipt().decisionImpact.status,'pending'); assert.deepEqual(f.receipt().groups.slice(0,2),before);
});
test('linked record edits and removal invalidate the assessment', t => {
  const f=fixture(t); f.write('src/app.js','change');
  assessDecision(f,'existing',['docs/decisions/DR-0001-original.md']); f.pass();
  f.write('docs/decisions/DR-0001-original.md','Changed choice');
  assert.match(f.run().stderr,/Decision impact assessment stale/);
  f.pass('--draft'); assert.equal(f.receipt().decisionImpact.status,'pending');
  rmSync(join(f.cwd,'docs/decisions/DR-0001-original.md'));
  assert.match(f.run().stderr,/Linked decision record missing/);
});
test('reviewing a proposed ADR does not approve it or write its contents', t => {
  const f=fixture(t); f.write('src/app.js','change'); const path='docs/decisions/DR-0002-new.md';
  const proposed='# Candidate choice\nStatus: Proposed\nDecider: Awaiting owner\n'; f.write(path,proposed);
  assessDecision(f,'create',[path]); f.pass(); assert.equal(f.read(path),proposed);
  assert.match(f.pass().stdout,/human acceptance are not certified/);
});
test('a new base resets decision assessment; repeated draft preserves reviewed state', t => {
  const f=fixture(t); f.write('src/app.js','change'); f.ready(); const before=f.receipt().decisionImpact;
  f.pass('--draft'); assert.deepEqual(f.receipt().decisionImpact,before);
  f.git('add','.'); f.commit(); f.pass('--base',f.base);
  f.write('tests/app.js','next task'); f.pass('--draft');
  assert.equal(f.receipt().decisionImpact.status,'pending'); assert.deepEqual(f.receipt().decisionImpact.records,[]);
});

// Pre-extraction fixes: schema, migration and deterministic guidance.
function guidanceFixture(t) {
 const f=fixture(t),record='docs/decisions/DR-0001-original.md';
 copyFileSync(resolve('.groundwork/core/sync-guidance.mjs'),join(f.cwd,'sync.mjs'));
 f.map.rules.push({id:'sync',prefixes:['sync.mjs'],docs:[]});
 f.map.guidanceMap='docs/guidance-map.json';
 f.write('docs/documentation-map.json',JSON.stringify(f.map));
 f.write('docs/guidance-map.json',JSON.stringify({version:1,topics:[{key:'scrolling',record,targets:['README.md','docs/experience.md']}]}));
 const data={version:1,id:'DR-0001',title:'Scrolling',status:'accepted',summary:['Show the start.'],rationale:'Preserve natural reading order.'};
 const source=()=>f.write(record,'# Decision\n<!-- groundwork:decision-summary:start -->\n```json\n'+JSON.stringify(data)+'\n```\n<!-- groundwork:decision-summary:end -->\n\nRationale and approval history.\n');source();
 const block='<!-- groundwork:generated:scrolling:start -->\n<!-- groundwork:generated:scrolling:end -->';
 f.write('README.md','Before\n'+block+'\nAfter\n');f.write('docs/experience.md',block+'\n');
 const sync=arg=>spawnSync(process.execPath,['sync.mjs',arg],{cwd:f.cwd,encoding:'utf8'});
 return {...f,data,source,sync,record};
}
test('guidance generates rationale and relative links; repeat write is idempotent',t=>{
 const f=guidanceFixture(t);assert.equal(f.sync('--write').status,0);const before=f.read('README.md');
 assert.match(before,/Why:.*Preserve natural reading order/);assert.match(before,/^Before\n/);assert.match(before,/\nAfter\n$/);
 assert.match(f.read('docs/experience.md'),/\]\(decisions\/DR-0001-original.md\)/);
 assert.equal(f.sync('--write').status,0);assert.equal(f.read('README.md'),before);assert.equal(f.sync('--check').status,0);
});
test('stale and missing-rationale guidance block only the affected operation',t=>{
 const f=guidanceFixture(t);f.sync('--write');f.data.rationale='New approved rationale.';f.source();const before=f.read('README.md');
 assert.match(f.sync('--check').stderr,/Stale generated/);assert.match(f.run('--draft').stderr,/Continue investigation/);
 delete f.data.rationale;f.source();assert.match(f.sync('--write').stderr,/rationale/);assert.equal(f.read('README.md'),before);
});
test('guidance validates all targets before writing and preserves manual text',t=>{
 const f=guidanceFixture(t);f.sync('--write');const before=f.read('README.md');f.data.summary=['Changed'];f.source();
 f.write('docs/experience.md','Missing markers');assert.notEqual(f.sync('--write').status,0);assert.equal(f.read('README.md'),before);
});
test('guidance rejects unaccepted records, duplicate markers and symlink targets',t=>{
 const f=guidanceFixture(t);f.data.status='proposed';f.source();assert.match(f.sync('--write').stderr,/accepted/);
 f.data.status='accepted';f.source();f.write('README.md',f.read('README.md')+f.read('README.md'));assert.notEqual(f.sync('--write').status,0);
 rmSync(join(f.cwd,'README.md'));f.git('restore','README.md');
 // symlink to another file in the fixture is still rejected.
 f.git('rm','README.md');execFileSync('ln',['-s','docs/experience.md','README.md'],{cwd:f.cwd});assert.match(f.sync('--write').stderr,/Symlink/);
});
test('clean Git tree still checks stale guidance and incompatible receipt shape',t=>{
 const f=guidanceFixture(t);f.sync('--write');f.data.summary=['Changed source'];f.source();f.git('add','.');f.commit();
 assert.match(f.run().stderr,/Stale generated/);f.sync('--write');f.git('add','.');f.commit();f.save({version:99});f.git('add','.');f.commit();assert.match(f.run().stderr,/format v3/);
});
test('both known v2 variants migrate with exact backups and pending assessments',t=>{
 for(const withDecision of [false,true]) {
 const f=fixture(t);f.write('src/app.js','change');f.ready();const r=f.receipt();r.version=2;if(!withDecision)delete r.decisionImpact;f.save(r);const before=f.read('docs/documentation-review.json');
 f.pass('--migrate');const after=f.receipt();assert.equal(after.version,3);assert.equal(after.base,r.base);
 for(const a of [...after.groups,after.projectContext,after.decisionImpact]){assert.equal(a.status,'pending');assert.equal(a.fingerprint,null);}
 const files=f.git('ls-files','--others','--exclude-standard').split('\n').filter(n=>n.startsWith('docs/history/'));
 assert.equal(files.length,1);assert.equal(f.read(files[0]),before);
 const bytes=f.read('docs/documentation-review.json');f.pass('--migrate');assert.equal(f.read('docs/documentation-review.json'),bytes);
 }
});
test('unknown fields, future versions and missing Git bases cannot be migrated',t=>{
 const f=fixture(t);f.write('src/app.js','change');f.ready();const original=f.receipt();
 for(const patch of [{version:2,unexpected:true},{version:4},{version:2,base:'f'.repeat(40)}]){
 f.save({...original,...patch});const before=f.read('docs/documentation-review.json');assert.notEqual(f.run('--migrate').status,0);assert.equal(f.read('docs/documentation-review.json'),before);
 }
});
test('core module changes invalidate reviews and schema changes require recompilation',t=>{
 const f=fixture(t);f.write('src/app.js','change');f.ready();f.write('groundwork/guidance.mjs',f.read('groundwork/guidance.mjs')+'\n// revision\n');assert.match(f.run().stderr,/Stale group/);
 f.write('groundwork/schemas/receipt-v3.schema.json',f.read('groundwork/schemas/receipt-v3.schema.json')+'\n');assert.match(f.run().stderr,/validators are stale/);
});
