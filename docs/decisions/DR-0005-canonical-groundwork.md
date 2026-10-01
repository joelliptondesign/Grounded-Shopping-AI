# DR-0005 Canonical Groundwork adoption

Status: Accepted direction; implemented locally
Date: 2026-10-01
Decider: J.L. (Phase 4 adoption); Codex (implementation details)
Scope: Repository maintenance; product governance is unchanged

## Context and alternatives

This repository supplied the mature Groundwork implementation. Continuing independent script copies across projects would permit drift; reading a mutable shared folder at runtime would reduce reproducibility.

## Decision and rationale

Adopt pinned Groundwork 0.1.0-rc.2 with local managed core, ownership hashes and the existing scripts commands as wrappers. Keep project configuration, product guidance, ADRs, generated scrolling guidance and the isolated Python verifier local. Preserve superseded modules under docs/history/pre-canonical-groundwork as historical evidence. Shared fixes belong upstream and arrive through reviewed updates.

J.L. authorized adoption with “proceed to phase 4.” This applies the approved canonical-source direction while keeping offline operation and project-specific rules. It does not authorize publication, live model calls, a new CI gate or changes to shopping behavior.

## Implementation, evidence and limits

A reviewed installer plan applied without collisions. Existing receipt v3 and generated scrolling guidance were retained. Local fixtures now exercise the installed core. See docs/work/GROUNDWORK-PHASE-4.md for verification. Prior uncommitted work, including .gitignore, was preserved. No browser or live-model acceptance is claimed for this tooling-only change.
