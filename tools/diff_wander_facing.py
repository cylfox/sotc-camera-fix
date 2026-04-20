"""Diff Wander facing direction A vs B (stable captures).
Look for unit-vector float triples that represent his body orientation,
plus ±π angle flips (180° rotation).
"""
import os, sys, struct, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "archive" / "scenarios"

with (OUT / "stable_wander_A.json").open() as f:
    sa = json.load(f)
with (OUT / "stable_wander_B.json").open() as f:
    sb = json.load(f)

diffs = []
for k, va in sa.items():
    if k in sb and sb[k] != va:
        diffs.append((int(k, 16), va, sb[k]))
diffs.sort(key=lambda d: d[0])

def asf(w):
    f = struct.unpack('<f', struct.pack('<I', w))[0]
    return f if -1e8 < f < 1e8 and f == f else None

d_map = {d[0]: d for d in diffs}

print(f"=== Unit-vector triples (candidates for body facing) ===")
for a in sorted(d_map.keys()):
    if a + 4 in d_map and a + 8 in d_map:
        v1 = d_map[a]; v2 = d_map[a+4]; v3 = d_map[a+8]
        f1 = asf(v1[1]); f2 = asf(v2[1]); f3 = asf(v3[1])
        g1 = asf(v1[2]); g2 = asf(v2[2]); g3 = asf(v3[2])
        if None in (f1, f2, f3, g1, g2, g3):
            continue
        m_a = (f1*f1 + f2*f2 + f3*f3) ** 0.5
        m_b = (g1*g1 + g2*g2 + g3*g3) ** 0.5
        if 0.98 < m_a < 1.02 and 0.98 < m_b < 1.02:
            # Is it ~180° flipped?
            dot = f1*g1 + f2*g2 + f3*g3
            tag = f" [UNIT]  dot={dot:+.3f}"
            if dot < -0.9:
                tag += " ~180° FLIP"
            print(f"  0x{a:08X}  ({f1:+.3f}, {f2:+.3f}, {f3:+.3f}) -> "
                  f"({g1:+.3f}, {g2:+.3f}, {g3:+.3f}){tag}")

print(f"\n=== Angle candidates (radians, +/-pi range) ===")
for a, va, vb in diffs:
    fa = asf(va); fb = asf(vb)
    if fa is None or fb is None:
        continue
    if abs(fa) < 3.5 and abs(fb) < 3.5:
        delta = fb - fa
        # 180° flip in radians ≈ ±π (3.14)
        tag = ""
        if abs(abs(delta) - math.pi) < 0.3 or abs(abs(delta) - math.pi*2) < 0.5:
            tag = " ~180° FLIP candidate"
        elif abs(fa) > 0.1 or abs(fb) > 0.1:
            tag = " (possible angle)"
        if tag:
            print(f"  0x{a:08X}  {fa:+.4f} -> {fb:+.4f}  (d={delta:+.3f}){tag}")

print(f"\nTotal diffs: {len(diffs)}")
