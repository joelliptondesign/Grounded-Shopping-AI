"""Small scoring and reporting helpers for Shopping Agent Core."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


SEVERITIES = ("critical", "major", "minor")


@dataclass
class CaseResult:
    case_id: str
    category: str
    dimensions: List[str]
    severity: str
    tags: List[str]
    passed: bool = True
    failures: List[Dict[str, Any]] = field(default_factory=list)
    criteria_checked: int = 0
    qualitative_pending: bool = False
    actual: Dict[str, Any] = field(default_factory=dict)
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def check(self, criterion: str, expected: Any, actual: Any) -> None:
        self.criteria_checked += 1
        passed = expected == actual
        self.checks.append({"criterion": criterion, "passed": passed})
        if not passed:
            self.passed = False
            self.failures.append(
                {"criterion": criterion, "expected": expected, "actual": actual}
            )

    def fail(self, criterion: str, expected: Any, actual: Any) -> None:
        self.check(criterion, expected, actual)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "dimensions": self.dimensions,
            "severity": self.severity,
            "tags": self.tags,
            "passed": self.passed,
            "criteria_checked": self.criteria_checked,
            "qualitative_pending": self.qualitative_pending,
            "failures": self.failures,
            "actual": self.actual,
            "checks": self.checks,
        }


def nested_get(value: Dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def flatten(value: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(flatten(item, path))
        else:
            flattened[path] = item
    return flattened


def summary(results: Iterable[CaseResult]) -> Dict[str, Any]:
    items = list(results)
    failures = [item for item in items if not item.passed]
    by_severity = Counter(item.severity for item in failures)
    by_dimension: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "failed": 0}
    )
    by_category: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "failed": 0}
    )
    for item in items:
        outcome = "passed" if item.passed else "failed"
        by_category[item.category][outcome] += 1
        for dimension in item.dimensions:
            by_dimension[dimension][outcome] += 1
    metric_patterns = {
        "intent_accuracy": lambda name: (name.endswith(".intent") or name == "intent") and ".state." not in name,
        "field_state_accuracy": lambda name: ".state." in name or name.startswith("state."),
        "candidate_set_accuracy": lambda name: name in {"candidate_ids", "candidate_set"},
        "expected_winner_accuracy": lambda name: name == "winner" or name.endswith(".winner"),
        "grounding_validator_accuracy": lambda name: name == "grounding.valid",
        "modality_selection_accuracy": lambda name: name == "modality" or name.endswith(".modality"),
        "recovery_transition_accuracy": lambda name: name.endswith(".recovery_type") or name.endswith(".extraction_error"),
    }
    metrics = {}
    for metric, matches in metric_patterns.items():
        checks = [check for item in items for check in item.checks if matches(check["criterion"])]
        metrics[metric] = {
            "passed": sum(check["passed"] for check in checks),
            "total": len(checks),
            "rate": round(sum(check["passed"] for check in checks) / len(checks), 4) if checks else None,
        }
    scored = [item.actual.get("manual_score") for item in items if item.actual.get("manual_score") is not None]
    return {
        "cases_run": len(items),
        "passed": sum(item.passed for item in items),
        "failed": len(failures),
        "failures_by_severity": {
            severity: by_severity.get(severity, 0) for severity in SEVERITIES
        },
        "qualitative_pending": sum(item.qualitative_pending for item in items),
        "by_dimension": dict(sorted(by_dimension.items())),
        "by_category": dict(sorted(by_category.items())),
        "metrics": metrics,
        "conversation_quality": {
            "scored_cases": len(scored),
            "average": round(sum(scored) / len(scored), 3) if scored else None,
        },
    }


def markdown_report(run: Dict[str, Any]) -> str:
    totals = run["summary"]
    lines = [
        "# Evaluation Run Report",
        "",
        f"- Suite: `{run['suite_name']}`",
        f"- Version: `{run['suite_version']}` (schema `{run['schema_version']}`)",
        f"- Run: `{run['created_at']}`",
        f"- Mode: `{run['mode']}`",
        f"- Cases: {totals['cases_run']} ({totals['passed']} passed, {totals['failed']} failed)",
        f"- Critical / major / minor failures: {totals['failures_by_severity']['critical']} / {totals['failures_by_severity']['major']} / {totals['failures_by_severity']['minor']}",
        f"- Qualitative cases awaiting a score: {totals['qualitative_pending']}",
        "",
        "## Evaluated configuration",
        "",
        f"- Model routing: `{run['configuration']['models']}`",
        f"- Prompt hashes: `{run['configuration']['prompt_hashes']}`",
        f"- Fixture version: `{run['configuration']['fixture_version']}`",
        f"- Code commit: `{run['configuration']['code_commit']}`",
        "",
        "## Critical invariants",
        "",
    ]
    for invariant, outcome in run["critical_invariants"].items():
        lines.append(f"- {'PASS' if outcome else 'FAIL'} — {invariant}")
    lines.extend(["", "## By dimension", "", "| Dimension | Passed | Failed |", "|---|---:|---:|"])
    for name, counts in totals["by_dimension"].items():
        lines.append(f"| {name.replace('_', ' ').title()} | {counts['passed']} | {counts['failed']} |")
    lines.extend(["", "## By scenario category", "", "| Category | Passed | Failed |", "|---|---:|---:|"])
    for name, counts in totals["by_category"].items():
        lines.append(f"| `{name}` | {counts['passed']} | {counts['failed']} |")
    lines.extend(["", "## Automated metrics", "", "| Metric | Passed | Total | Rate |", "|---|---:|---:|---:|"])
    for name, metric in totals["metrics"].items():
        rate = "n/a" if metric["rate"] is None else f"{metric['rate']:.1%}"
        lines.append(f"| {name.replace('_', ' ').title()} | {metric['passed']} | {metric['total']} | {rate} |")
    conversation = totals["conversation_quality"]
    lines.extend(["", "## Conversation quality", ""])
    if conversation["scored_cases"]:
        lines.append(f"{conversation['scored_cases']} cases have manual scores; average: {conversation['average']:.2f}/3.")
    else:
        lines.append("No manual scores are recorded, so no conversation-quality average is reported.")
    lines.extend(["", "## Failure details", ""])
    failed = [item for item in run["results"] if not item["passed"]]
    if not failed:
        lines.append("No automated criteria failed.")
    for item in failed:
        lines.extend([f"### {item['case_id']} ({item['severity']})", ""])
        for failure in item["failures"]:
            lines.append(
                f"- `{failure['criterion']}` — expected `{failure['expected']}`, actual `{failure['actual']}`"
            )
        lines.append("")
    if not failed:
        lines.append("")
    lines.extend(["## Qualitative scoring", ""])
    pending = [item for item in run["results"] if item["qualitative_pending"]]
    if not pending:
        lines.append("No qualitative responses are awaiting review.")
    else:
        lines.append("These outputs are prepared for manual 0–3 scoring; no unreviewed score is included in metrics.")
        lines.append("")
        for item in pending:
            lines.append(f"- `{item['case_id']}`")
    lines.append("")
    return "\n".join(lines)
