"""Find an aim-specific flag: aim differs from free, swim, AND colossus.

Requires stable_aim.json, stable_free.json, stable_swim.json,
stable_colossus.json under archive/scenarios/.

Ideal: aim has one value, all three non-aim states have another (same)
value. That flag, gated in Trampoline A, covers every non-aim state
we've sampled.
"""
import json, struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "archive" / "scenarios"

def load(name):
    with (OUT / name).open() as f:
        return json.load(f)

am = load("stable_aim.json")
fr = load("stable_free.json")
sw = load("stable_swim.json")
co = load("stable_colossus.json")

clean = []
for k, vam in am.items():
    if k not in fr or k not in sw or k not in co:
        continue
    vfr = fr[k]
    vsw = sw[k]
    vco = co[k]
    if vam == vfr or vam == vsw or vam == vco:
        continue
    clean.append((int(k, 16), vam, vfr, vsw, vco))

# Purest: free == swim == colossus, aim differs from all
all_eq = [c for c in clean if c[2] == c[3] == c[4]]
all_eq.sort(key=lambda c: max(c[1], c[2]))

print(f"[*] {len(clean)} addrs: stable in all 4, aim differs from each other state")
print(f"[*] {len(all_eq)} also have free == swim == colossus (purest aim-only)\n")

print("=== Purest aim-only flags (free == swim == colossus, aim differs) ===")
for a, vam, vfr, vsw, vco in all_eq[:50]:
    hint = "  [clean 0/1]" if vam < 2 and vfr < 2 else ""
    print(f"  0x{a:08X}  aim=0x{vam:08X} free=0x{vfr:08X} swim=0x{vsw:08X} col=0x{vco:08X}{hint}")

print("\n=== Weaker candidates (aim differs from each, but non-aim values don't match) ===")
weaker = [c for c in clean if not (c[2] == c[3] == c[4])]
weaker.sort(key=lambda c: max(c[1], c[2], c[3], c[4]))
for a, vam, vfr, vsw, vco in weaker[:20]:
    print(f"  0x{a:08X}  aim=0x{vam:08X} free=0x{vfr:08X} swim=0x{vsw:08X} col=0x{vco:08X}")
