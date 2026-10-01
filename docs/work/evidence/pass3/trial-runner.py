# Reproduction helper: original installation baseline and known failures assumed.
from pathlib import Path
import importlib.util,json,subprocess,tempfile,shutil
src=Path('/Users/joellipton/Desktop/Grounded-Shopping-AI')
out=Path(tempfile.mkdtemp(prefix='groundwork-pass3-evidence-'))
print('Trial evidence:', out, flush=True)
spec=importlib.util.spec_from_file_location('offline',src/'scripts/verify-offline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(tempfile.mkdtemp(prefix='groundwork-pass3-'));(out/'fixture-location.txt').write_text(str(root))
results=[]
for name in ['frontend','engine','evaluation']:
 r=root/name;r.mkdir();m.source_snapshot(src,r)
 def run(args,ok=True):
  p=subprocess.run(args,cwd=r,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  if ok and p.returncode:raise RuntimeError(p.stdout)
  return p
 def git(*args):return run(['git',*args]).stdout.strip()
 git('init','-q');git('add','.');git('-c','user.name=Groundwork trial','-c','user.email=trial@example.invalid','commit','-qm','Isolated baseline')
 def edit(path,a,b):
  p=r/path;s=p.read_text();assert a in s;p.write_text(s.replace(a,b,1))
 if name=='frontend':
  target='frontend/Rufus Shopping Agent.dc.html';edit(target,'Ask a shopping question','Ask about mattresses');docs=['frontend/README.md'];disposition='no-impact';reason='Composer placeholder clarified; rendering, modes, API boundary and documented interaction behavior are unchanged.'
 elif name=='engine':
  target='engine/customer_copy.py';edit(target,"I don't have reliable information about that for this mattress.","I don’t have verified information about that for this mattress.");docs=['GOVERNANCE.md','docs/ARCHITECTURE.md'];disposition='no-impact';reason='Unknown-fact wording changed while its evidence boundary, fallback conditions and documented behavior remain unchanged.'
 else:
  target='tests/test_groundwork_trial.py';(r/target).write_text("import unittest\nfrom engine.customer_copy import product_fact_fallback, UNKNOWN_FACT\nclass MissingEvidence(unittest.TestCase):\n def test_unverified_result_does_not_disclose_product_claim(self):\n  self.assertEqual(product_fact_fallback({'verified':False,'product':{'name':'Unsupported claim'}}), UNKNOWN_FACT)\n")
  edit('docs/EVALUATION.md','## Workflow','The isolated Groundwork trial adds an unverified-fact regression: a supplied product claim must not escape when verification is false.\n\n## Workflow')
  docs=['docs/EVALUATION.md'];disposition='updated';reason='Evaluation guidance now describes the additional unverified-fact regression; dataset gold expectations remain unchanged.'
 report=json.loads(run(['node','scripts/check-docs.mjs','--report']).stdout)
 assert sorted(x['doc'] for x in report['targets'])==sorted(docs)
 assert run(['node','scripts/check-docs.mjs'],False).returncode!=0
 run(['node','scripts/check-docs.mjs','--draft'])
 rec=r/'docs/documentation-review.json';d=json.loads(rec.read_text())
 for g in d['groups']:g.update(status='reviewed',disposition=disposition,reason=reason,reviewer='Codex controlled trial')
 d['projectContext'].update(status='reviewed',changed=False,reason='Trial preserves summarized product capabilities, scope, constraints and existing known gaps.',reviewer='Codex controlled trial')
 rec.write_text(json.dumps(d,indent=2));run(['node','scripts/check-docs.mjs'])
 # A second area gets its own group while prior groups remain reviewed.
 other='engine/customer_copy.py' if name=='frontend' else 'frontend/Rufus Shopping Agent.dc.html'
 p=r/other;s=p.read_text();p.write_text(s+'\n' if other.endswith('.py') else s.replace('Ask a shopping question','Ask about mattress options',1))
 run(['node','scripts/check-docs.mjs','--draft']);d2=json.loads(rec.read_text());assert all(next(g for g in d2['groups'] if g['documents']==g0['documents'])['status']=='reviewed' for g0 in d['groups'])
 p.write_text(s);run(['node','scripts/check-docs.mjs','--draft'])
 # Relevant follow-up invalidates previous review, even an innocuous byte change.
 p=r/target;before=p.read_text();p.write_text(before+'\n');assert run(['node','scripts/check-docs.mjs'],False).returncode!=0
 run(['node','scripts/check-docs.mjs','--draft']);assert all(g['status']=='pending' for g in json.loads(rec.read_text())['groups'])
 p.write_text(before);rec.write_text(json.dumps(d,indent=2));run(['node','scripts/check-docs.mjs'])
 verification=run([str(src/'.venv/bin/python'),'scripts/verify-offline.py'],False)
 assert verification.returncode==1,verification.stdout
 evidence=Path(verification.stdout.split('Evidence: ')[1].splitlines()[0]);summary=json.loads((evidence/'summary.json').read_text());assert summary['results']=={'unit':(1 if name=='engine' else 0),'eval':1}
 reports=list((evidence/'source/artifacts/evals/shopping-agent-core/v2').glob('*report.md'));text=reports[0].read_text();assert '25 passed, 1 failed' in text and 'expected `S04`, actual `S22`' in text
 caseout=out/name;caseout.mkdir(exist_ok=True)
 for f in ['unit.log','eval.log','summary.json']:shutil.copy2(evidence/f,caseout/f)
 (caseout/'trial.patch').write_text(git('diff','--',target,'docs/EVALUATION.md'))
 if name=='evaluation':shutil.copy2(r/target,caseout/'trial-test.py')
 result={'scenario':name,'review_targets':docs,'disposition':disposition,'unrelated_review_preserved':True,'relevant_edit_invalidated':True,'unit_exit':summary['results']['unit'],'evaluation_exit':1,'known_failure':'v2_compare_and_pick_001: S04 vs S22','context_rewrite':False}
 results.append(result);print(json.dumps(result),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print('FIXTURES',root)
