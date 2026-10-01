# Groundwork Pass 2 verification

September 30, 2026 · Local installation complete; representative workflow trials remain for Pass 3.

## Installed

- A dependency-free Node documentation checker adapted from the tested portfolio implementation, with project-specific routing and historical evaluation boundaries.
- A grouped review record with selective invalidation and a short Project Context assessment.
- A Python offline runner that tests an isolated source snapshot, excludes credentials and old execution artifacts, and retains its logs and reports in a temporary folder.
- Maintained workflow/setup instructions. No application source, prompts, fixtures, gold expectations, or prior evaluation records were changed.

## Verification

- 26 documentation-checker regression tests passed: review lifecycle, stale content, new bases, staged/working distinction, review preservation, large-file byte changes, historical target restrictions, and shopping-project routing.
- Two offline-runner regression tests passed: any suite failure remains nonzero; snapshots reflect working/untracked source while excluding environment/history/ignored files and rejecting symlinks.
- The actual offline run passed all 193 application unit tests.
- Core v2 validated 26 cases and passed 25, with all nine critical invariants passing. The known major failure remains v2_compare_and_pick_001, turn 3 expected S04 versus actual S22. Eleven qualitative cases remain unscored.
- The offline runner returned 1 for that failure. This is expected baseline reproduction, not a green full evaluation.

Evidence from the actual run: `/var/folders/pl/zcgmjwkx6x786k5fv04_8s0r0000gn/T/groundwork-offline-ip1_e7zm/`. summary.json holds revision and source hashes; unit.log and eval.log hold command output; the source copy contains generated evaluation results. Temporary evidence is subject to OS cleanup. The report's revision field is unavailable in the isolated copy; summary.json identifies source baseline d45eae6 and the working-file contents used.

The verified snapshot preceded final documentation edits, which do not change application behavior or the runner. Documentation review was completed afterward against the final change.

## Limits and preservation

No browser acceptance, live model evaluation, latency/cost measurement, remote CI, hooks, nightly task, commit, push, or deployment occurred. Pass 1 and Pass 2 remain local uncommitted additions. The existing .gitignore change is preserved and included in working-tree review coverage without being authored or staged by this installation.

The offline Python network guard is a safeguard for trusted tests, not isolation of arbitrary subprocesses. Tests still require the existing Python dependencies; documentation checking requires Node 22+ and Git. The unresolved scrolling conflict remains unchanged. Pass 3 should exercise realistic frontend, engine/prompt, and evaluation changes and verify agent cold-start use.
