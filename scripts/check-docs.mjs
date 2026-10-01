import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, renameSync, existsSync, lstatSync, openSync, readSync, closeSync, fstatSync } from 'node:fs';
import { createHash } from 'node:crypto';

const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trimEnd();
const list = (...args) => git(...args).split('\0').filter(Boolean);
const hash = value => createHash('sha256').update(value).digest('hex');
const digest = value => hash(JSON.stringify(value));
const receiptPath = 'docs/documentation-review.json';
const contextPath = 'docs/PROJECT-STATE.md';
const mapPath = 'docs/documentation-map.json';
const args = process.argv.slice(2);
const fail = message => { throw Error(message); };
const text = value => typeof value === 'string' && value.trim().length >= 20;
const unique = values => [...new Set(values)].sort();
try {
  if (args.includes('--staged')) fail('Documentation review checks working files, not the staged index. Do not insert this command into the staged-content hook.');
  let revision = 'HEAD', mode = 'check';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--base' && args[i + 1] && !args[i + 1].startsWith('--')) revision = args[++i];
    else if (['--report', '--draft'].includes(args[i]) && mode === 'check') mode = args[i].slice(2);
    else fail('Usage: check-docs.mjs [--base REV] [--report | --draft]');
  }
  process.chdir(git('rev-parse', '--show-toplevel'));
  const base = git('rev-parse', '--verify', `${revision}^{commit}`);
  if (list('diff', '--name-only', '--diff-filter=U', '-z').length) fail('Resolve merge conflicts before documentation review');
  const map = JSON.parse(readFileSync(mapPath, 'utf8'));
  const untracked = list('ls-files', '--others', '--exclude-standard', '-z');
  const excludedUntracked = untracked.filter(p => !p.includes('/') && (map.untrackedNonSiteExtensions || []).some(ext => p.endsWith(ext)));
  if (excludedUntracked.length) console.error('Outside site review (untracked only; contents not read): ' + excludedUntracked.join(', '));
  const changed = unique([...list('diff', '--name-only', '--no-renames', '-z', base, '--'), ...untracked.filter(p => !excludedUntracked.includes(p))]).filter(p => p !== receiptPath);
  if (!Array.isArray(map.rules) || !map.rules.length || unique(map.rules.map(r => r.id)).length !== map.rules.length) fail('Invalid or duplicate map rules');
  for (const r of map.rules) if (typeof r.id !== 'string' || !Array.isArray(r.prefixes) || !r.prefixes.length || r.prefixes.some(p => typeof p !== 'string' || !p) || !Array.isArray(r.docs)) fail('Invalid map rule');
  const safeDoc = p => typeof p === 'string' && !p.startsWith('/') && !p.split('/').includes('..') && !p.startsWith('docs/archive/') && !p.startsWith('docs/baseline/') && !p.startsWith('docs/history/') && !p.startsWith('artifacts/') && p.endsWith('.md');
  for (const doc of unique(map.rules.flatMap(r => r.docs))) if (!safeDoc(doc) || !existsSync(doc)) fail(`Mapped document missing or invalid: ${doc}`);
  if (!existsSync(contextPath)) fail(`Project Context missing: ${contextPath}`);
  const classifications = {}, affected = new Set();
  for (const path of changed) {
    const rules = map.rules.filter(r => r.prefixes.some(prefix => path.startsWith(prefix)));
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
  const engine = hash(readFileSync(new URL(import.meta.url)));
  const inputsFor = doc => changed.filter(p => classifications[p].some(r => r.docs.includes(doc)));
  const rulesFor = doc => map.rules.filter(r => r.docs.includes(doc)).sort((a, b) => a.id.localeCompare(b.id));
  const groupFingerprint = group => {
    if (!Array.isArray(group.documents) || !group.documents.length || group.documents.some(d => !safeDoc(d) || !existsSync(d))) fail('Group documents must be existing, nonhistorical Markdown paths');
    if (!Array.isArray(group.evidence) || group.evidence.some(p => typeof p !== 'string' || !changed.includes(p) || historical(p))) fail('Evidence must name current nonhistorical changed paths');
    return digest({ base, engine, docs: unique(group.documents).map(doc => ({ doc: snapshot(doc), rules: rulesFor(doc), inputs: inputsFor(doc).map(snapshot) })), evidence: unique(group.evidence).map(snapshot) });
  };
  // This one short assessment covers the whole change, including un-routed docs.
  const contextFingerprint = digest({ base, engine, map, context: snapshot(contextPath), changes: changed.filter(p => !historical(p)).map(snapshot) });
  const targets = [...affected].sort().map(doc => ({ doc, inputs: inputsFor(doc) }));
  if (mode === 'report') {
    console.log(JSON.stringify({ version: 2, base, changed, excludedUntracked, targets, projectContextFingerprint: contextFingerprint }, null, 2));
    process.exit(0);
  }
  if (!changed.length) { console.log('Documentation impact: no changes against selected base. Use --base REV for committed work.'); process.exit(0); }
  const prior = existsSync(receiptPath) ? JSON.parse(readFileSync(receiptPath, 'utf8')) : null;
  if (mode === 'draft') {
    const groups = [], covered = new Set();
    if (prior?.version === 2 && prior.base === base && Array.isArray(prior.groups)) {
      for (const old of prior.groups) {
        if (!Array.isArray(old.documents)) continue;
        const documents = unique(old.documents).filter(d => safeDoc(d) && existsSync(d) && !covered.has(d));
        if (!documents.length) continue;
        // Remove obsolete paths from a draft; never silently re-accept it.
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
    const oldContext = prior?.version === 2 ? prior.projectContext : null;
    const projectContext = oldContext && prior.base === base && oldContext.fingerprint === contextFingerprint ? oldContext : {
      status: 'pending', changed: null, reason: '', reviewer: '', fingerprint: contextFingerprint,
    };
    const draft = { version: 2, base, groups, projectContext };
    writeFileSync(`${receiptPath}.tmp`, JSON.stringify(draft, null, 2) + '\n');
    renameSync(`${receiptPath}.tmp`, receiptPath);
    console.log(`Draft saved: ${groups.filter(g => g.status === 'reviewed').length} retained reviewed groups; ${groups.filter(g => g.status !== 'reviewed').length} pending groups; Project Context ${projectContext.status}. Review pending items before setting status to reviewed.`);
    process.exit(0);
  }
  if (!prior) fail('Documentation review missing. Run node scripts/check-docs.mjs --draft.');
  if (prior.version !== 2) fail('Review format v2 required. Run --draft to replace the legacy record with an unreviewed draft; Git retains prior history.');
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
  if (errors.length) fail(errors.join('\n'));
  console.log(`Documentation impact passed: ${changed.length} changed files; ${prior.groups.length} review groups; Project Context assessed. Semantic accuracy and human acceptance are not certified.`);
} catch (error) { console.error(`Documentation impact failed: ${error.message}`); process.exit(1); }
