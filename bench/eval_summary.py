"""Compact CX + integrity summary for a calibration run artifact."""
import json, sys

run = json.load(open(sys.argv[1]))
print("mode:", run["mode"], "| cases:", run["summary"]["cases_run"],
      "passed:", run["summary"]["passed"], "failed:", run["summary"]["failed"])
print("CX overall average:", round(run["shopping_experience_summary"]["overall_average"], 2), "/3")
for item in run["results"]:
    judgment = item["shopping_experience"]["judgment"]
    criteria = judgment.get("criteria") or {}
    scores = " ".join(f"{k}={v.get('score') if isinstance(v, dict) else v}" for k, v in criteria.items())
    print(f"  {item['case_id']:<40} cx={judgment['overall_score']}/3  "
          f"integrity={item['system_integrity']['status']}  det={item['deterministic_regression_passed']}")
    if scores:
        print(f"      {scores}")
