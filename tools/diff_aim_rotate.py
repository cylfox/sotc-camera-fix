"""Diff aim_neutral vs aim_rotating — find fields the aim system writes
to drive Wander's rotation (and camera rotation).

Prioritize:
  - Unit-vector float triples (these are likely direction vectors)
  - Fields in entity region (0x01301000+) and camera/input region (0x01060000+)
"""
import os, sys, struct, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "archive" / "scenarios"

with (OUT / "stable_aim_neutral.json").open() as f:
    sn = json.load(f)
with (OUT / "stable_aim_rotating.json").open() as f:
    sr = json.load(f)

diffs = []
for k, vn in sn.items():
    if k in sr and sr[k] != vn:
        diffs.append((int(k, 16), vn, sr[k]))
diffs.sort(key=lambda d: d[0])

def asf(w):
    f = struct.unpack('<f', struct.pack('<I', w))[0]
    return f if -1e8 < f < 1e8 else None

# Float triples (consecutive 3 floats that changed)
print(f"=== Unit-vector triples (candidate direction fields) ===")
d_map = {d[0]: d for d in diffs}
for a in sorted(d_map.keys()):
    if a + 4 in d_map and a + 8 in d_map:
        v1 = d_map[a]; v2 = d_map[a+4]; v3 = d_map[a+8]
        f1 = asf(v1[1]); f2 = asf(v2[1]); f3 = asf(v3[1])
        g1 = asf(v1[2]); g2 = asf(v2[2]); g3 = asf(v3[2])
        if None in (f1, f2, f3, g1, g2, g3):
            continue
        m_n = (f1*f1 + f2*f2 + f3*f3) ** 0.5
        m_r = (g1*g1 + g2*g2 + g3*g3) ** 0.5
        tag = ""
        if 0.98 < m_n < 1.02 and 0.98 < m_r < 1.02:
            tag = " [UNIT vector]"
        elif 0.98 < m_n < 1.02 or 0.98 < m_r < 1.02:
            tag = " [one-side unit]"
        if tag:
            print(f"  0x{a:08X}  ({f1:+.3f}, {f2:+.3f}, {f3:+.3f}) -> "
                  f"({g1:+.3f}, {g2:+.3f}, {g3:+.3f}){tag}")

print(f"\n=== Small-delta float diffs (slow-moving state) ===")
shown = 0
for a, vn, vr in diffs:
    fn = asf(vn); fr = asf(vr)
    if fn is None or fr is None:
        continue
    if abs(fn) < 100 and abs(fr) < 100 and abs(fn - fr) > 0.001:
        # Reasonably-scaled values
        if shown < 40:
            print(f"  0x{a:08X}  {fn:+.4f} -> {fr:+.4f}  (delta {fr-fn:+.4f})")
            shown += 1

print(f"\n=== ALL diffs ===")
for a, vn, vr in diffs:
    fn = asf(vn); fr = asf(vr)
    print(f"  0x{a:08X}  0x{vn:08X} -> 0x{vr:08X}  ({fn:+.4f} -> {fr:+.4f})")

print(f"\nTotal diffs (both stable): {len(diffs)}")
