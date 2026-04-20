"""Find a swim-specific flag: stable in all 3 states, swim differs from aim.

Requires stable_swim.json, stable_aim.json, stable_free.json under
archive/scenarios/ (produced by find_stable_flags.py).

Identified 0x0106AD90 for the v11 swim gate (swim=1 / aim=0 / free=0).
"""
import json, struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "archive" / "scenarios"

def load(name):
    with (OUT / name).open() as f:
        return json.load(f)

sw = load("stable_swim.json")
am = load("stable_aim.json")
fr = load("stable_free.json")

# Candidate: stable in all 3; swim != aim; ideally aim == free
# (so the new gate fires only in swim, never in aim or free-roam).
clean = []
for k, vsw in sw.items():
    if k not in am or k not in fr:
        continue
    vam = am[k]
    vfr = fr[k]
    if vsw == vam:
        continue
    clean.append((int(k, 16), vsw, vam, vfr))

aim_equals_free = [c for c in clean if c[2] == c[3]]
aim_equals_free.sort(key=lambda c: max(c[1], c[2], c[3]))

print(f"[*] {len(clean)} addrs stable in all 3, swim != aim")
print(f"[*] {len(aim_equals_free)} also have aim == free (purest swim-only signal)\n")

print("=== Purest swim-only flags (aim == free, swim differs) ===")
for a, vsw, vam, vfr in aim_equals_free[:40]:
    hint = "  [clean 0/1]" if vsw < 2 and vam < 2 else ""
    print(f"  0x{a:08X}  swim=0x{vsw:08X} aim=0x{vam:08X} free=0x{vfr:08X}{hint}")
