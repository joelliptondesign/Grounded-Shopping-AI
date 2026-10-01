# Decision impact: Pass 1

October 1, 2026. Implementation within the existing Groundwork impact-review workflow.

- Added one decisionImpact assessment to the existing version-2 receipt and commands. Dispositions: none, existing, update, create. Records use the current numbered Markdown format; the ADR template is unchanged.
- Added trigger criteria and routine-work exemptions to maintained guidance. Planning/discovery identifies choices before dependent work; completion reconciles the same assessment.
- Validation requires a completed explanation/reviewer, unique existing record paths, record actions consistent with the selected Git base, and a current fingerprint. Linked record changes and whole-task changes reopen assessment. Unaffected documentation groups retain their reviews. A new base starts fresh.
- Approval remains in the ADR. The checker never edits approval status or determines whether a choice was authorized. A proposed record can be recorded accurately without authorizing implementation.
- Both existing offline-runner regression tests pass.
- All 35 checker tests pass (26 existing plus nine focused decision-impact tests). Coverage includes missing/legacy assessments, invalid dispositions/reasons/links, existing/update/create consistency, new change bases, staleness, retained unrelated document reviews, and unchanged proposed status.

Application source, product evaluation criteria and frontend behavior are unchanged in this pass. No live calls, hook/CI installation, commit or push. The pre-existing local .gitignore edit is preserved. Existing v2 review receipts must be redrafted to add the pending field. The source-copy offline runner is unchanged.

Pass 2 remains: exercise this during realistic routine, existing-decision and new-decision work, assess overhead and tighten only if those trials expose gaps. Focused tests are not a claim that agents will always classify decisions correctly.
