"""Perceived latency: when the shopper first sees useful grounded content.

Baseline buffered the whole turn, so nothing structured appeared until the prose
was written and validated: first useful content == total turn, plus the
frontend's fixed pre-roll and loading floor. Streaming surfaces the validated
structured result at presentation-ready instead.
"""
import json, sys

BASE_PREROLL = 420 + 400   # demo-scripted submit beat + minimum dots dwell
OPT_PREROLL = 80           # live pre-roll; the progress state itself lands here

def pct(values, q=0.5):
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    return clean[min(len(clean) - 1, int(round(q * (len(clean) - 1))))] if clean else None

base = json.load(open(sys.argv[1]))
opt = json.load(open(sys.argv[2]))
STRUCTURED = {"strong_rec", "exploratory_rec", "refinement", "comparison", "product_question"}

print(f"{'scenario':<20}{'baseline first useful':>22}{'optimized first useful':>24}{'improvement':>14}")
for name in base:
    if name not in opt or not opt[name] or name == "see_more":
        continue
    b = pct([s["total_turn"] for s in base[name]])
    o = pct([s["presentation_ready"] if name in STRUCTURED else s["total_turn"] for s in opt[name]])
    if b is None or o is None:
        continue
    b += BASE_PREROLL
    o += OPT_PREROLL
    kind = "cards/table" if name in STRUCTURED else "prose"
    print(f"{name:<20}{b:>17.0f} ms{o:>19.0f} ms ({kind}){(o-b)/b*100:>+9.0f}%")
print(f"\n{'progress state visible':<20}{BASE_PREROLL:>17} ms{OPT_PREROLL:>19} ms{(OPT_PREROLL-BASE_PREROLL)/BASE_PREROLL*100:>+18.0f}%")
