"""Stage-level latency benchmark for the Live shopping-agent pipeline.

Drives real turns through the API and reports per-stage timings. Scenarios mirror
the Live journeys the prototype supports.
"""

import argparse, json, statistics, sys, time, urllib.request

BASE = "http://localhost:8000"

SCENARIOS = {
    "cold_start":        [("I need a mattress", None)],
    "strong_rec":        [("I need a queen mattress around $1400. Cooling and motion isolation matter most.", None)],
    "exploratory_rec":   [("Just show me some queen mattresses", None)],
    "refinement":        [("I need a queen around $1400, cooling matters most", None),
                          ("Show me something closer to $1,100", "measure")],
    "comparison":        [("I need a queen around $1400, cooling matters most", None),
                          ("Compare the first two", "measure")],
    "product_question":  [("I need a queen around $1400, cooling matters most", None),
                          ("Which sleeps coolest?", "measure")],
    "review_question":   [("I need a queen around $1400, cooling matters most", None),
                          ("What do customers say?", "measure")],
    "service_question":  [("I need a queen around $1400, cooling matters most", None),
                          ("Does the first one include haul-away?", "measure")],
    "see_more":          [("I need a queen around $1400, cooling matters most", None),
                          ("__SEE_MORE__", "measure")],
    "elicitation_click": [("I need a mattress", None), ("Queen", "measure")],
}


def post(path, body=None, timeout=240):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read() or b"{}")
    return payload, (time.perf_counter() - started) * 1000


def run_scenario(steps):
    sid = post("/api/session")[0]["session_id"]
    measured = None
    last_recs = None
    for message, mark in steps:
        if message == "__SEE_MORE__":
            body = {"category": last_recs["items"][0]["role"],
                    "shown": [i["id"] for i in last_recs["items"]]}
            out, wall = post(f"/api/session/{sid}/more", body)
        else:
            out, wall = post(f"/api/session/{sid}/turn", {"message": message})
        recs = next((b for b in out.get("blocks", []) if b["kind"] == "recs"), None)
        if recs:
            last_recs = recs
        if mark == "measure" or len(steps) == 1:
            measured = (out, wall)
    return measured


def sample(out, wall):
    debug = out.get("debug") or {}
    metrics = (debug.get("latency") or {}).get("metrics_ms") or {}
    return {
        "http_wall": wall,
        "modality": debug.get("modality"),
        "strategy": debug.get("response_strategy"),
        "extraction": metrics.get("extraction_latency"),
        "routing": metrics.get("routing_latency"),
        "deterministic_decision": metrics.get("deterministic_decision_latency"),
        "shopping_selection": metrics.get("shopping_selection_latency"),
        "decision_ready": metrics.get("decision_ready_latency"),
        "presentation_ready": metrics.get("presentation_ready_latency"),
        "generation_ttft": metrics.get("generation_ttft"),
        "generation": metrics.get("generation_latency"),
        "total_turn": metrics.get("total_turn_latency"),
    }


def pct(values, q):
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    if not clean:
        return None
    index = min(len(clean) - 1, int(round(q * (len(clean) - 1))))
    return clean[index]


STAGES = ["extraction", "routing", "deterministic_decision", "shopping_selection",
          "decision_ready", "presentation_ready", "generation_ttft", "generation",
          "total_turn", "http_wall"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    names = [args.only] if args.only else list(SCENARIOS)
    results = {}
    for name in names:
        samples = []
        for run in range(args.runs):
            try:
                measured = run_scenario(SCENARIOS[name])
                if measured:
                    samples.append(sample(*measured))
            except Exception as error:
                print(f"  {name} run {run+1} failed: {type(error).__name__}: {error}", file=sys.stderr)
        results[name] = samples
        if samples:
            print(f"\n{name}  (n={len(samples)}, modality={samples[-1]['modality']}, strategy={samples[-1]['strategy']})")
            for stage in STAGES:
                values = [s[stage] for s in samples]
                p50, p90 = pct(values, 0.5), pct(values, 0.9)
                if p50 is not None:
                    print(f"   {stage:<24} p50 {p50:8.0f} ms   p90 {p90:8.0f} ms")
    if args.out:
        json.dump(results, open(args.out, "w"), indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
