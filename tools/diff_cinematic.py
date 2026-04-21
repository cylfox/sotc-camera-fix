"""Find a cinematic-specific flag: cinematic differs from all gameplay states.

Requires stable_cinematic.json plus any subset of:
  stable_free.json, stable_swim.json, stable_aim.json, stable_colossus.json,
  stable_precinematic.json

Ideal: cinematic has one value; all gameplay states have the same (different)
value. Such a flag cleanly marks "cinematic playing" and nothing else.
"""
import json, struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "archive" / "scenarios"

def load(name):
    path = OUT / name
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)

cin = load("stable_cinematic.json")
gameplay = {
    "free": load("stable_free.json"),
    "swim": load("stable_swim.json"),
    "aim": load("stable_aim.json"),
    "colossus": load("stable_colossus.json"),
    "precinematic": load("stable_precinematic.json"),
}
gameplay = {k: v for k, v in gameplay.items() if v is not None}

print(f"[*] Comparing cinematic against: {', '.join(gameplay.keys())}")

# Keep addresses stable in ALL loaded states and in cinematic;
# where cinematic != every other state's value.
clean = []
for k, vcin in cin.items():
    if any(k not in v for v in gameplay.values()):
        continue
    if any(gameplay[n][k] == vcin for n in gameplay):
        continue
    clean.append((int(k, 16), vcin, {n: gameplay[n][k] for n in gameplay}))

# Purest: all gameplay states share one value, cinematic differs
purest = []
for a, vcin, vothers in clean:
    unique_gameplay_vals = set(vothers.values())
    if len(unique_gameplay_vals) == 1:
        purest.append((a, vcin, next(iter(unique_gameplay_vals))))
purest.sort(key=lambda c: max(c[1], c[2]))

print(f"[*] {len(clean)} addrs stable everywhere, cinematic value differs from each")
print(f"[*] {len(purest)} also have all gameplay states agree (purest cinematic signal)\n")

print("=== Purest cinematic-only flags (all gameplay values equal, cinematic differs) ===")
for a, vcin, vgame in purest[:50]:
    hint = "  [clean 0/1]" if vcin < 2 and vgame < 2 else ""
    print(f"  0x{a:08X}  cin=0x{vcin:08X}  all gameplay=0x{vgame:08X}{hint}")
