# Evaluation Suites

Evaluation definitions use the hierarchy **concept → version**. Executions are stored separately as immutable run artifacts.

- [Shopping Agent Core](shopping-agent-core/README.md) — versioned deterministic and live behavior cases used by the independent System Integrity and Shopping Experience judges.
- [Shopping Experience Calibration](shopping_experience_calibration.py) — the fixed five-case live calibration runner; it preserves complete journeys and writes under `artifacts/evals/shopping-experience-calibration/v1/`.
- [Conversational Reference Continuity](conversational-reference-continuity/v1/journeys.json) — six focused live journeys over recent UI identity/order, compare→pick continuity, topic carryover, and genuine ambiguity; the runner writes immutable evidence under `artifacts/evals/conversational-reference-continuity/v1/`.
- [Evaluation run index](../artifacts/evals/INDEX.md) — reports and raw results for every recorded execution.
