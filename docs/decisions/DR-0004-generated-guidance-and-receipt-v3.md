# DR-0004 Generated guidance and explicit receipt schema

Status: Accepted direction; implemented and verified through Fix Pass 3
Date: October 1, 2026
Decider: J.L. (direction, rationale amendment and work-continuation boundary); Codex (implementation within scope)
Scope: Local Groundwork pre-extraction fixes in Shopping AI

## Context

The root CLAUDE entry point retained an unresolved scrolling claim after DR-0001 was accepted. Shopping and portfolio also both labeled incompatible receipt fields as version 2. Both issues need correction before canonical extraction.

## Options and recommendation

Stable links alone avoid duplicates but require agents to open destinations. Generated summaries plus links provide immediate rules from an authoritative source. Selected: a bounded deterministic generator, not an LLM summarizer or repository-wide prose rewriter. A separately versioned receipt schema replaces implicit field conventions.

## Decision and rationale

Use marked JSON metadata in the ADR, an explicit topic map and generated marked sections. Include the approved concise rationale so instructions preserve intent. Keep full rationale, alternatives and approval history in the ADR. Select accepted records explicitly; generation does not grant authority.

Use schema v3 with required decisionImpact and explicit migration from both known v2 variants. Preserve original receipt bytes and compatible authored content, but reset assessments to pending. Compile schema validation into shipped code so routine commands remain offline and require no npm installation.

Incomplete metadata stops the affected operation or completion claim, not all work. Continue investigation, documentation repair and independent authorized implementation; pause only work that depends on unresolved intent or authority. The user explicitly rejected a repository-wide work stoppage for missing fields.

Source: J.L. approved the rationale amendment, accepted the scoped-blocking explanation, and requested moving to the next fix pass. This authorizes implementation of those contracts, not publication or automatic approval of later product decisions.

## Evidence and consequences

[Installed contracts](../workflow/GROUNDWORK-CONTRACTS.md) and [Fix Pass 2 report](../work/PRE-EXTRACTION-FIX-PASS-2.md). Build tooling uses pinned development dependencies; Node/Git remain the normal runtime prerequisites. Original scrolling behavior and approval history are retained. The portfolio installation is unchanged.

## Acceptance and follow-up

Eight isolated Fix Pass 3 trials verified the combined lifecycle, explicit supersession, migration, fault recovery and bounded command overhead. [Evidence and limits](../work/PRE-EXTRACTION-FIX-PASS-3.md). No additional policy decision was needed. Canonical extraction is the next planned phase. No commit, push, deployment or canonical repository is created by this pass.
