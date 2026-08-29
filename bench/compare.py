"""Baseline vs optimized, by stage."""
import json, sys

def pct(values, q):
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    if not clean:
        return None
    return clean[min(len(clean) - 1, int(round(q * (len(clean) - 1))))]

base = json.load(open(sys.argv[1]))
opt = json.load(open(sys.argv[2]))
STAGES = [("presentation_ready", "first useful visible"), ("total_turn", "turn complete")]
print(f"{'scenario':<20}{'metric':<24}{'baseline p50':>13}{'opt p50':>10}{'delta':>10}{'  base p90':>11}{'opt p90':>10}")
for name in base:
    for key, label in STAGES:
        b50, o50 = pct([s[key] for s in base[name]], .5), pct([s[key] for s in opt.get(name, [])], .5)
        b90, o90 = pct([s[key] for s in base[name]], .9), pct([s[key] for s in opt.get(name, [])], .9)
        if b50 is None or o50 is None:
            continue
        delta = f"{(o50-b50)/b50*100:+.0f}%"
        print(f"{name:<20}{label:<24}{b50:>10.0f} ms{o50:>7.0f} ms{delta:>10}{b90:>8.0f} ms{o90:>7.0f} ms")
