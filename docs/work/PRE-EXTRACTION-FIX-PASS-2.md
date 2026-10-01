# Pre-extraction fixes: Pass 2

October 1, 2026 · Implemented locally; broader Fix Pass 3 trials pending.

## Delivered

- DR-0001 now owns structured scrolling metadata including the approved concise rationale. Full rationale, alternatives, decision source and historical evidence remain in the record.
- Explicit topic mapping generates marked summaries and relative links in AGENTS.md, CLAUDE.md, frontend/CLAUDE.md and frontend/README.md. Removed the root CLAUDE stale unresolved claim. Project Context and the source map point to the authoritative record; the index no longer independently repeats the pilot status.
- Schema v3 is enforced by bundled Ajv-generated validators. No runtime npm installation or network calls are needed. Development-only build dependencies are pinned; a clean npm ci and build succeeded.
- Explicit migration preserves either known v2 shape, original base and compatible text, backs up exact original bytes, and resets assessments to pending. Unknown versions and fields fail without overwriting the receipt. Shopping's actual receipt was migrated; the portfolio was not modified.
- Guidance checks run before clean-tree success. Module/schema and configured source changes invalidate freshness. Checks never auto-generate, approve decisions or edit application code.
- Missing metadata blocks the affected command or completion claim, not independent authorized work. Instructions and command errors make this scope explicit.

## Verification

All 43 checker tests pass, including eight new generation/migration tests and updated schema-aware lifecycle fixtures. [Test output](pre-extraction-fix2-checker-tests.txt). Both existing offline-runner regression tests pass. Guidance check passes, generation is idempotent in the focused tests, and the original migration backup is preserved. A fresh pinned validator build was verified separately from the project's runtime. No product or browser suite was needed for these tooling/guidance changes; no live model calls were made.

The focused suite exercises rationale output, nested relative links, source staleness, missing required rationale, all-target marker preflight, manual text preservation, unaccepted sources, duplicate markers, symlink rejection, clean-tree checks, both v2 migrations, exact backups, repeated migration, invalid schemas/versions/bases, module freshness and schema recompilation requirements.

## Limits and next pass

These are implementation tests, not independent-agent or long-term drift evidence. Fix Pass 3 still needs representative combined workflow trials, accepted-successor selection, broader error/recovery cases and overhead review. Generation does not synchronize arbitrary unregistered prose or authenticate acceptance. Migration backup is not a substitute for reviewing the v3 assessments.

Application source, scrolling behavior, the shopping offline runner, existing user ignore edits and the real portfolio installation are preserved. No canonical repository, installer, hook, CI gate, schedule, commit or push was created. See [DR-0004](../decisions/DR-0004-generated-guidance-and-receipt-v3.md) and [installed contracts](../workflow/GROUNDWORK-CONTRACTS.md).
