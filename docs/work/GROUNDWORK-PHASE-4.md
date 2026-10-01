# Canonical Groundwork adoption: Phase 4

October 1, 2026 · Adopted locally · Groundwork 0.1.0-rc.2

## Result

The reviewed installer plan applied with no conflicts. The same candidate now produces a repeat plan with zero changes and no conflicts. Core and wrapper hashes are pinned in .groundwork/installation.json. Local knowledge and routing remain project-owned. Application code and existing hook/CI definitions were preserved.

## Verification

43 documentation regression tests; two isolated-runner tests; 198 mocked unit tests; 26/26 deterministic Core v2 cases; generated guidance current.

[Project test output](groundwork-phase4-shopping-tests.txt). The documentation receipt records the final impact review against current working contents. This report records verified local adoption. Commit and remote publication status are tracked by Git; these checks do not certify deployment. Canonical source revision: 473c132201a1078c638e5cabb11e1c8b896c69df, published through cd0e3f2.

## Adaptation and boundaries

Regression fixtures now load the complete installed core, including its fingerprinted shared guidance. Portfolio fixtures were updated for explicit migration and strict v3 record shapes; assertions were not bypassed. Missing metadata blocks the affected check, not independent work.

No browser review, live model calls, production deployment, independent-agent usability or long-term drift effectiveness was tested. A passing receipt records review completeness and freshness; semantic review remains the agent/human responsibility.

The superseded local modules were archived byte-for-byte under docs/history/pre-canonical-groundwork. Existing ADRs, generated scrolling guidance, .gitignore and prior product changes were preserved. Offline evaluation ran in an isolated snapshot and left artifacts/evals/INDEX.md unchanged. No receipt migration was needed because Shopping already used v3.
