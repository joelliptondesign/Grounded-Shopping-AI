# Generated guidance and receipt v3

Installed October 1, 2026 · Fix Pass 2 implementation · Eight isolated Fix Pass 3 workflow trials complete. [Evidence and limits](../work/PRE-EXTRACTION-FIX-PASS-3.md).

## Authority and scope

The [guidance map](../guidance-map.json) selects one current record per topic and lists its destinations. The selected ADR contains one marked JSON block with version, id, title, status, summary and rationale. The generator copies those fields and adds a relative link to the full record. It never selects the newest ADR or interprets approval prose. Only accepted, nonsuperseded selected records supply active instructions. Metadata declares status; it does not authenticate the decider.

For the scrolling pilot, [DR-0001](../decisions/DR-0001-scrolling-conflict.md) owns the rule and concise rationale. Authored rationale, alternatives, historical approval and evidence remain in the full record. A change to the rule needs the authorized decision, not just an edited status field.

Generated sections use topic-specific start/end comments. Explicit write replaces only those sections, validates all destinations first, detects changed source/destination contents, and reports written files if a write fails. Multiple writes are not an atomic transaction. Check is read-only. Missing/duplicate/nested/reversed/orphan markers fail rather than guessing. Repeated generation is a no-op. Proposals are not automatically activated; supersession requires an explicit accepted source and map update.

A stale summary or missing metadata blocks the affected generation or completion check. Investigation, repairs and unrelated authorized work can continue. Read the authoritative record directly if it clearly supplies the approved rule. Pause dependent implementation only for unresolved authority or intent. Missing metadata does not erase documented approval, and completing metadata does not grant approval.

## Receipt contract

The [v3 schema](../../.groundwork/core/groundwork/schemas/receipt-v3.schema.json) defines root version/base/groups/projectContext/decisionImpact and each section's fields. [Source metadata schema](../../.groundwork/core/groundwork/schemas/decision-summary-v1.schema.json) and [map schema](../../.groundwork/core/groundwork/schemas/guidance-map-v1.schema.json) define guidance inputs. Runtime Ajv-generated validators reject unknown fields and invalid shapes. Pending assessments may retain draft explanations and null hashes; reviewed assessments must be complete. Passing schema validation alone is not passing completion review.

Repository checks still enforce coverage, links, real changes and freshness. none means no record links; existing means unchanged records at the selected base; update requires a changed existing record and no new records; create requires a new record. Reasons must be at least 20 characters after trimming. Review never certifies semantic accuracy or human acceptance.

Explicit migration accepts two known v2 shapes: with or without decisionImpact. Compatible values and the selected base are preserved. Every assessment becomes pending and every fingerprint null; absent decisionImpact becomes an empty pending assessment. Exact original bytes are backed up by content hash before atomic receipt replacement. A fresh draft binds the current inputs; no legacy fingerprints are reused. Unknown versions/fields, unsafe paths or missing base objects stop migration without replacing the original. Existing v3 is validated and left unchanged.

Commands and completion order are in the [working process](README.md). The map requires guidance checking even on a clean tree. A clean result does not certify an old receipt against a different base. Configured guidance dependencies, modules and schemas participate in freshness checks. Historical migration backups are excluded from current review contents.

## Implementation limits

Generation covers the declared sections, not every paraphrase in the repository. Schema validation does not evaluate rationale quality. Git worktree checks are not staged-index checks. This local cooperative process is not a security boundary or an automatic organization-wide approval system. No external model, policy engine, CI installation or scheduling is involved.
