# Groundwork third-candidate update

October 1, 2026 · Implemented and verified; J.L. authorized commit and push. Git history records publication.

J.L. authorized the reviewed three-project update plan with “ok lets proceed.” Installed version is **0.1.0-rc.3**, the third release candidate for version 0.1.0. The reviewed installer changed only the ownership/version manifest; the project-owned decision template was adapted separately. Runtime and schema versions are unchanged. Existing adoption direction remains in [DR-0005-canonical-groundwork](../decisions/DR-0005-canonical-groundwork.md).

## Changes and verification

- Added the optional structured decision example with rationale, generation markers, schema locations and acceptance instructions. Existing authored project guidance is preserved.
- Existing generated scrolling guidance is current and unchanged.
- 43 documentation regression tests passed against the installed core.
- The actual adapted template passed schema validation, proposed-source rejection and synthetic accepted-source generation in a disposable fixture. Rule, rationale, source link, authored destination preservation and repeat-generation idempotence passed. Synthetic acceptance never modified a real record.
- A fresh installer plan returned no changes or conflicts after adaptation.
- Documentation impact review is recorded in [the receipt](../documentation-review.json); completion is verified against the isolated publication snapshot, excluding unrelated working-tree changes.

No application code, real decision acceptance, runtime/schema contracts, hooks, CI or scheduled tasks changed. No receipt migration was needed. Full UI suites and live model evaluations were not rerun because this update changes only version metadata, authoring guidance and documentation. Automatic template update notices remain unimplemented.

The pre-existing `.gitignore` edit is preserved and excluded from this task’s publication scope. The committed review is bound to the publication snapshot without that unrelated edit; the local working tree still contains it and needs its own review when that edit is committed.
