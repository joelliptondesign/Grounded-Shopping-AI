import { loadConfig } from './groundwork/config.mjs';
import { validate, coreIdentity, boundary } from './groundwork/runtime.mjs';
import { syncGuidance } from './groundwork/guidance.mjs';
import { migrate } from './groundwork/migration.mjs';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, renameSync, existsSync, lstatSync, openSync, readSync, closeSync, fstatSync } from 'node:fs';
import { createHash } from 'node:crypto';

const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trimEnd();
const list = (...args) => git(...args).split('\0').filter(Boolean);
const hash = value => createHash('sha256').update(value).digest('hex');
const digest = value => hash(JSON.stringify(value));
const args = process.argv.slice(2);
const fail = message => { throw Error(message); };
const text = value => typeof value === 'string' && value.trim().length >= 20;
const unique = values => [...new Set(values)].sort();
try {
  if (args.includes('--staged')) fail('Documentation review checks working files, not the staged index. Do not insert this command into the staged-content hook.');
  let revision = 'HEAD', mode = 'check', configName;
  for (let i = 0; i < args.length; i++) {
    if(args[i] === '--config' && args[i+1] && !args[i+1].startsWith('--')) configName=args[++i];
    else if (args[i] === '--base' && args[i + 1] && !args[i + 1].startsWith('--')) revision = args[++i];
    else if (['--report', '--draft', '--migrate'].includes(args[i]) && mode === 'check') mode = args[i].slice(2);
    else fail('Usage: check-docs.mjs [--config PATH] [--base REV] [--report | --draft | --migrate]');
  }
  process.chdir(git('rev-parse', '--show-toplevel'));
  const config = loadConfig(process.cwd(),configName);
  const {receiptPath,contextPath,mapPath,decisionsDirectory}=config;
  if (mode === 'migrate') { if(args.includes('--base')) fail('--migrate preserves the receipt base; do not combine with --base'); console.log(migrate(process.cwd(),receiptPath,config.migrationBackupDirectory)); process.exit(0); }
  const base = git('rev-parse', '--verify', `${revision}^{commit}`);
  if (list('diff', '--name-only', '--diff-filter=U', '-z').length) fail('Resolve merge conflicts before documentation review');
  const map = JSON.parse(readFileSync(mapPath, 'utf8'));
  const guidance = syncGuidance(process.cwd(), config.guidanceMap ?? map.guidanceMap, {historicalPrefixes:config.historicalPrefixes});
  const prior = existsSync(receiptPath) ? JSON.parse(readFileSync(receiptPath, 'utf8')) : null;
  if(prior) {
    if(prior.version !== 3) { if(mode === 'report') console.error('Receipt is incompatible; explicit --migrate is required for supported v2.'); else fail('Review format v3 required. Use --migrate for known v2 receipts; unknown versions are preserved.'); }
    else validate('receiptV3',prior);
  }
  const untracked = list('ls-files', '--others', '--exclude-standard', '-z');
  const excludedUntracked = untracked.filter(p => !p.includes('/') && (map.untrackedNonSiteExtensions || []).some(ext => p.endsWith(ext)));
  if (excludedUntracked.length) console.error('Outside site review (untracked only; contents not read): ' + excludedUntracked.join(', '));
  const changed = unique([...list('diff', '--name-only', '--no-renames', '-z', base, '--'), ...untracked.filter(p => !excludedUntracked.includes(p))]).filter(p => p !== receiptPath);
  if (!Array.isArray(map.rules) || !map.rules.length || unique(map.rules.map(r => r.id)).length !== map.rules.length) fail('Invalid or duplicate map rules');
  for (const r of map.rules) if (typeof r.id !== 'string' || !Array.isArray(r.prefixes) || !r.prefixes.length || r.prefixes.some(p => typeof p !== 'string' || !p) || !Array.isArray(r.docs)) fail('Invalid map rule');
  const safeDoc = p => typeof p === 'string' && !p.startsWith('/') && !p.split('/').includes('..') && !config.historicalPrefixes.some(prefix=>p.startsWith(prefix)) && p.endsWith('.md');
  for (const doc of unique(map.rules.flatMap(r => r.docs))) if (!safeDoc(doc) || !existsSync(doc)) fail(`Mapped document missing or invalid: ${doc}`);
  if (!existsSync(contextPath)) fail(`Project Context missing: ${contextPath}`);
  const classifications = {}, affected = new Set();
  for (const path of changed) {
    const rules = map.rules.filter(r => r.prefixes.some(prefix => path.startsWith(prefix)) && !(r.excludePrefixes || []).some(prefix => path.startsWith(prefix)));
    if (!rules.length) fail(`Unmapped changed file: ${path}. Classify it in ${mapPath}.`);
    classifications[path] = rules;
    rules.forEach(r => r.docs.forEach(d => affected.add(d)));
  }
  const historical = p => classifications[p]?.every(r => r.historical === true);
  const snapshots = new Map();
  const snapshot = p => {
    if (snapshots.has(p)) return snapshots.get(p);
    if (historical(p)) return [p, 'historical-change']; // Never read archived content.
    if (!existsSync(p)) return [p, 'deleted'];
    const stat = lstatSync(p);
    if (!stat.isFile()) fail(`Unsupported file type: ${p}`);
    const fd = openSync(p, 'r');
    const digest = createHash('sha256');
    const chunk = Buffer.alloc(1024 * 1024);
    try {
      const before = fstatSync(fd);
      let count;
      while ((count = readSync(fd, chunk, 0, chunk.length, null)) > 0) digest.update(chunk.subarray(0, count));
      const after = fstatSync(fd);
      if (before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs) fail(`File changed while hashing: ${p}; rerun after edits settle`);
    } finally { closeSync(fd); }
    const value = [p, stat.mode & 0o777, digest.digest('hex')];
    snapshots.set(p, value);
    return value;
  };
  const engine = digest({checker: hash(readFileSync(new URL(import.meta.url))), core: coreIdentity(), config, guidance: guidance.fingerprint});
  const inputsFor = doc => changed.filter(p => classifications[p].some(r => r.docs.includes(doc)));
  const rulesFor = doc => map.rules.filter(r => r.docs.includes(doc)).sort((a, b) => a.id.localeCompare(b.id));
  const groupFingerprint = group => {
    if (!Array.isArray(group.documents) || !group.documents.length || group.documents.some(d => !safeDoc(d) || !existsSync(d))) fail('Group documents must be existing, nonhistorical Markdown paths');
    if (!Array.isArray(group.evidence) || group.evidence.some(p => typeof p !== 'string' || !changed.includes(p) || historical(p))) fail('Evidence must name current nonhistorical changed paths');
    return digest({ base, engine, docs: unique(group.documents).map(doc => ({ doc: snapshot(doc), rules: rulesFor(doc), inputs: inputsFor(doc).map(snapshot) })), evidence: unique(group.evidence).map(snapshot) });
  };
  // This one short assessment covers the whole change, including un-routed docs.
  const contextFingerprint = digest({ base, engine, map, context: snapshot(contextPath), changes: changed.filter(p => !historical(p)).map(snapshot) });
  // One decision assessment per checkpoint; reuse the whole-change binding.
  const recordPath = p => typeof p === 'string' && p.startsWith(decisionsDirectory+'/') && /^DR-\d{4}-[a-z0-9-]+\.md$/.test(p.slice(decisionsDirectory.length+1));
  const decisionFingerprint = records => digest({
    contextFingerprint,
    guidance: config.decisionGuidance.map(snapshot),
    records: unique(records).map(snapshot),
  });
  const targets = [...affected].sort().map(doc => ({ doc, inputs: inputsFor(doc) }));
  if (mode === 'report') {
    console.log(JSON.stringify({ version: 3, base, changed, excludedUntracked, targets, projectContextFingerprint: contextFingerprint, decisionImpactRequired: changed.length > 0 }, null, 2));
    process.exit(0);
  }
  if (!changed.length) { console.log('Documentation impact: no changes against selected base. Use --base REV for committed work.'); process.exit(0); }
  if (mode === 'draft') {
    const groups = [], covered = new Set();
    if (prior?.version === 3 && prior.base === base && Array.isArray(prior.groups)) {
      for (const old of prior.groups) {
        if (!Array.isArray(old.documents)) continue;
        const documents = unique(old.documents).filter(d => safeDoc(d) && existsSync(d) && !covered.has(d));
        if (!documents.length) continue;
        // Remove obsolete paths from a draft; never silently re-accept it.
        const removed = (old.evidence || []).filter(p => !changed.includes(p) || historical(p));
        if(removed.length) console.error('Draft removed obsolete evidence: '+removed.join(', '));
        if(documents.length !== old.documents.length) console.error('Draft removed obsolete document targets; consult prior receipt backup/history.');
        const evidence = Array.isArray(old.evidence) ? old.evidence.filter(p => changed.includes(p) && !historical(p)) : [];
        if (!evidence.length && documents.every(d => !affected.has(d) && !changed.includes(d))) continue;
        const candidate = { ...old, documents, evidence };
        const fingerprint = groupFingerprint(candidate);
        const unchanged = prior.base === base && old.fingerprint === fingerprint;
        groups.push({ ...candidate, fingerprint, status: unchanged ? old.status : 'pending' });
        documents.forEach(d => covered.add(d));
      }
    }
    for (const { doc, inputs } of targets) if (!covered.has(doc)) {
      const group = { documents: [doc], status: 'pending', disposition: null, reason: '', evidence: inputs.filter(p => !historical(p)), reviewer: '' };
      groups.push({ ...group, fingerprint: groupFingerprint(group) });
    }
    const oldContext = prior?.version === 3 ? prior.projectContext : null;
    const projectContext = oldContext && prior.base === base && oldContext.fingerprint === contextFingerprint ? oldContext : {
      status: 'pending', changed: null, reason: '', reviewer: '', fingerprint: contextFingerprint,
    };
    const oldDecision = prior?.version === 3 && prior.base === base ? prior.decisionImpact : null;
    const records = Array.isArray(oldDecision?.records) ? unique(oldDecision.records.filter(recordPath)) : [];
    const fingerprint = decisionFingerprint(records);
    const decisionImpact = oldDecision && oldDecision.fingerprint === fingerprint ? oldDecision : {
      status: 'pending', disposition: oldDecision?.disposition ?? null,
      reason: oldDecision?.reason ?? '', reviewer: oldDecision?.reviewer ?? '', records, fingerprint,
    };
    const draft = { version: 3, base, groups, projectContext, decisionImpact };
    validate('receiptV3', draft);
    writeFileSync(`${receiptPath}.tmp`, JSON.stringify(draft, null, 2) + '\n');
    renameSync(`${receiptPath}.tmp`, receiptPath);
    console.log(`Draft saved: ${groups.filter(g => g.status === 'reviewed').length} retained reviewed groups; ${groups.filter(g => g.status !== 'reviewed').length} pending groups; Project Context ${projectContext.status}; decision impact ${decisionImpact.status}. Review pending items before setting status to reviewed.`);
    process.exit(0);
  }
  if (!prior) fail('Documentation review missing. Run node scripts/check-docs.mjs --draft.');
  if (prior.base !== base) fail('Review uses another base; run --draft with the intended --base.');
  if (!Array.isArray(prior.groups)) fail('Review groups must be an array');
  const covered = new Set(), errors = [];
  for (const group of prior.groups) {
    const fingerprint = groupFingerprint(group);
    for (const doc of group.documents) {
      if (covered.has(doc)) errors.push(`Duplicate review coverage: ${doc}`);
      covered.add(doc);
      if (group.disposition === 'updated' && !changed.includes(doc)) errors.push(`Document marked updated but unchanged: ${doc}`);
    }
    const name = group.documents.join(', ');
    if (group.fingerprint !== fingerprint) errors.push(`Stale group: ${name}. Relevant source, evidence, document, rules, or checker changed.`);
    if (group.status !== 'reviewed') errors.push(`Pending group: ${name}`);
    if (!['updated', 'no-impact'].includes(group.disposition) || !text(group.reason) || typeof group.reviewer !== 'string' || !group.reviewer.trim() || !group.evidence.length) errors.push(`Incomplete disposition, explanation, evidence, or reviewer: ${name}`);
  }
  for (const doc of affected) if (!covered.has(doc)) errors.push(`Missing coverage: ${doc}`);
  const c = prior.projectContext;
  if (!c || c.status !== 'reviewed' || typeof c.changed !== 'boolean' || !text(c.reason) || typeof c.reviewer !== 'string' || !c.reviewer.trim()) errors.push('Project Context assessment missing or pending');
  if (c?.fingerprint !== contextFingerprint) errors.push('Project Context assessment stale; reconsider the short impact answer for the current change');
  if (c?.changed === true && !changed.includes(contextPath)) errors.push('Project Context marked changed but has no diff');
  const d = prior.decisionImpact;
  const dispositions = ['none', 'existing', 'update', 'create'];
  if (!d || d.status !== 'reviewed' || !dispositions.includes(d.disposition) || !text(d.reason) || typeof d.reviewer !== 'string' || !d.reviewer.trim()) errors.push('Decision impact assessment missing, pending, or incomplete');
  if (!Array.isArray(d?.records) || d.records.some(p => !recordPath(p)) || unique(d.records).length !== d.records.length) {
    errors.push(`Decision records must be unique ${decisionsDirectory}/DR-NNNN-title.md paths`);
  } else {
    if (d.fingerprint !== decisionFingerprint(d.records)) errors.push('Decision impact assessment stale; run --draft and reassess the current change and linked records');
    const present = d.records.filter(p => existsSync(p));
    if (present.length !== d.records.length) errors.push('Linked decision record missing');
    if (d.disposition === 'none' && d.records.length) errors.push('Decision disposition none must not link records');
    if (d.disposition !== 'none' && !d.records.length) errors.push('Decision disposition requires at least one linked record');
    // Validate the claimed record work against the selected base, not its approval.
    const baseRecords = new Set(list('ls-tree', '-r', '--name-only', '-z', base, '--', decisionsDirectory));
    const newRecords = present.filter(p => !baseRecords.has(p));
    const updatedRecords = present.filter(p => !newRecords.includes(p) && changed.includes(p));
    if (d.disposition === 'existing' && (newRecords.length || updatedRecords.length)) errors.push('Existing decision disposition requires unchanged records from the selected base');
    if (d.disposition === 'update' && (!updatedRecords.length || newRecords.length)) errors.push('Update decision disposition requires a changed existing record and no new records');
    if (d.disposition === 'create' && !newRecords.length) errors.push('Create decision disposition requires a new record relative to the selected base');
  }
  if (errors.length) fail(errors.join('\n'));
  console.log(`Documentation impact passed: ${changed.length} changed files; ${prior.groups.length} review groups; Project Context and decision impact assessed. Semantic accuracy and human acceptance are not certified.`);
} catch (error) { console.error(`Documentation impact failed: ${error.message}\n${boundary}`); process.exit(1); }
