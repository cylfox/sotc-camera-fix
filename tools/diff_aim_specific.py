"""Find an aim-specific flag: aim differs from BOTH free-roam AND swim.

Ideal: aim == X, free == swim == Y. Then the v11 remap gate can become
"fire only when aim-flag == X", covering all non-aim states (free, swim,
climb, cutscene, ...) with the fallback deadzone path.
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

# Candidate: stable in all 3; aim != free AND aim != swim
clean = []
for k, vam in am.items():
    if k not in sw or k not in fr:
        continue
    vsw = sw[k]
    vfr = fr[k]
    if vam == vfr or vam == vsw:
        continue
    clean.append((int(k, 16), vam, vfr, vsw))

# Purest: free == swim (so aim is truly the odd one out across both non-aim states we sampled)
free_eq_swim = [c for c in clean if c[2] == c[3]]
free_eq_swim.sort(key=lambda c: max(c[1], c[2], c[3]))

print(f"[*] {len(clean)} addrs stable in all 3 with aim differing from both others")
print(f"[*] {len(free_eq_swim)} also have free == swim (purest aim-only signal)\n")

print("=== Purest aim-only flags (free == swim, aim differs) ===")
for a, vam, vfr, vsw in free_eq_swim[:40]:
    hint = "  [clean 0/1]" if vam < 2 and vfr < 2 else ""
    print(f"  0x{a:08X}  aim=0x{vam:08X} free=0x{vfr:08X} swim=0x{vsw:08X}{hint}")
