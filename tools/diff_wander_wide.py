"""Broader diff of wander_A vs wander_B — show all types of candidates."""
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
    return f if -1e10 < f < 1e10 and f == f else None

d_map = {d[0]: d for d in diffs}

# Find all consecutive 3-float triples in the entity region
print(f"=== Float triples in entity region (0x01301000-0x01303000) ===")
for a in sorted(d_map.keys()):
    if not (0x01301000 <= a < 0x01303000):
        continue
    if a + 4 in d_map and a + 8 in d_map:
        v1 = d_map[a]; v2 = d_map[a+4]; v3 = d_map[a+8]
        f1 = asf(v1[1]); f2 = asf(v2[1]); f3 = asf(v3[1])
        g1 = asf(v1[2]); g2 = asf(v2[2]); g3 = asf(v3[2])
        if None in (f1, f2, f3, g1, g2, g3):
            continue
        m_a = (f1*f1 + f2*f2 + f3*f3) ** 0.5
        m_b = (g1*g1 + g2*g2 + g3*g3) ** 0.5
        tag = ""
        if 0.98 < m_a < 1.02 and 0.98 < m_b < 1.02:
            dot = f1*g1 + f2*g2 + f3*g3
            tag = f" [UNIT]  dot={dot:+.3f}"
        print(f"  0x{a:08X}  ({f1:+.3f}, {f2:+.3f}, {f3:+.3f}) "
              f"|{m_a:.2f}| -> ({g1:+.3f}, {g2:+.3f}, {g3:+.3f}) |{m_b:.2f}|{tag}")

print(f"\n=== All entity-region diffs ===")
for a, va, vb in diffs:
    if not (0x01301000 <= a < 0x01303000):
        continue
    fa = asf(va); fb = asf(vb)
    print(f"  0x{a:08X}  0x{va:08X} -> 0x{vb:08X}  ({fa:+.4f} -> {fb:+.4f})")

print(f"\n=== All unit-vector triples (any region) ===")
seen = set()
for a in sorted(d_map.keys()):
    if a in seen:
        continue
    if a + 4 in d_map and a + 8 in d_map:
        v1 = d_map[a]; v2 = d_map[a+4]; v3 = d_map[a+8]
        f1 = asf(v1[1]); f2 = asf(v2[1]); f3 = asf(v3[1])
        g1 = asf(v1[2]); g2 = asf(v2[2]); g3 = asf(v3[2])
        if None in (f1, f2, f3, g1, g2, g3):
            continue
        m_a = (f1*f1 + f2*f2 + f3*f3) ** 0.5
        m_b = (g1*g1 + g2*g2 + g3*g3) ** 0.5
        if 0.98 < m_a < 1.02 and 0.98 < m_b < 1.02:
            dot = f1*g1 + f2*g2 + f3*g3
            tag = ""
            if dot < -0.85:
                tag = " ~OPPOSITE (~180 deg flip)"
            elif dot < 0.15:
                tag = " ~90 deg"
            elif dot > 0.85:
                tag = " nearly same"
            print(f"  0x{a:08X}  ({f1:+.3f}, {f2:+.3f}, {f3:+.3f}) -> "
                  f"({g1:+.3f}, {g2:+.3f}, {g3:+.3f})  dot={dot:+.3f}{tag}")
            seen.update([a, a+4, a+8])

print(f"\nTotal diffs: {len(diffs)}")
