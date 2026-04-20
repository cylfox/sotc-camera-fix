"""Diff the aimcam_free / aimcam_aim captures — find the aim-direction field.

Prioritize CAMERA POSE region (0x0106E000) and CAMERA CONTROLLER region
(0x01C18000) since those hold the forward vector we care about. Report
float-triples (potential direction vectors) and any clean integer flags.
"""
import os, sys, struct, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "archive" / "scenarios"

with (OUT_DIR / "stable_idle3.json").open() as f:
    sf = json.load(f)
with (OUT_DIR / "stable_aim3.json").open() as f:
    sa = json.load(f)

# All stable-in-both-states addresses with different values
diffs = []
for k, vf in sf.items():
    if k in sa and sa[k] != vf:
        diffs.append((int(k, 16), vf, sa[k]))

# Sort by address
diffs.sort(key=lambda d: d[0])

def as_float(w):
    f = struct.unpack('<f', struct.pack('<I', w))[0]
    if -1e8 < f < 1e8 and not (f != f):  # not NaN
        return f
    return None

# Focus: camera pose (0x0106E000..0x0106F000) and camera controller (0x01C18000..)
print(f"=== Camera pose region (0x0106E000..0x0106F000) ===")
pose_diffs = [d for d in diffs if 0x0106E000 <= d[0] < 0x0106F000]
for a, vf, va in pose_diffs:
    fv = as_float(vf)
    av = as_float(va)
    if fv is not None and av is not None:
        # unit-vector-ish float (usually -1..1)
        tag = ""
        if -2 < fv < 2 and -2 < av < 2:
            tag = " [unit-ish]"
        print(f"  0x{a:08X}  0x{vf:08X} -> 0x{va:08X}   ({fv:+.4f} -> {av:+.4f}){tag}")
    else:
        print(f"  0x{a:08X}  0x{vf:08X} -> 0x{va:08X}")

print(f"\n=== Camera controller region (0x01C18000..+0x2000) ===")
ctrl_diffs = [d for d in diffs if 0x01C18000 <= d[0] < 0x01C1A000]
for a, vf, va in ctrl_diffs:
    fv = as_float(vf)
    av = as_float(va)
    if fv is not None and av is not None:
        tag = ""
        if -2 < fv < 2 and -2 < av < 2:
            tag = " [unit-ish]"
        print(f"  0x{a:08X}  0x{vf:08X} -> 0x{va:08X}   ({fv:+.4f} -> {av:+.4f}){tag}")
    else:
        print(f"  0x{a:08X}  0x{vf:08X} -> 0x{va:08X}")

# Float triples (consecutive 3 floats that both differ) in BOTH regions
print(f"\n=== Candidate float triples (consecutive 3-float vectors that changed) ===")
all_diffs_by_addr = {d[0]: d for d in diffs}
for a in sorted(all_diffs_by_addr.keys()):
    # Check if a, a+4, a+8 all appear as diffs
    if a + 4 in all_diffs_by_addr and a + 8 in all_diffs_by_addr:
        v1 = all_diffs_by_addr[a]
        v2 = all_diffs_by_addr[a + 4]
        v3 = all_diffs_by_addr[a + 8]
        # Float interpretations
        f1 = as_float(v1[1]); f2 = as_float(v2[1]); f3 = as_float(v3[1])
        a1 = as_float(v1[2]); a2 = as_float(v2[2]); a3 = as_float(v3[2])
        if (f1 is not None and f2 is not None and f3 is not None and
            a1 is not None and a2 is not None and a3 is not None):
            # Check if looks like a unit vector
            mag_free = (f1*f1 + f2*f2 + f3*f3) ** 0.5
            mag_aim = (a1*a1 + a2*a2 + a3*a3) ** 0.5
            tag = ""
            if 0.98 < mag_free < 1.02 and 0.98 < mag_aim < 1.02:
                tag = " [UNIT VECTOR]"
            elif 0.98 < mag_free < 1.02 or 0.98 < mag_aim < 1.02:
                tag = " [one-side unit]"
            print(f"  0x{a:08X}  ({f1:+.3f}, {f2:+.3f}, {f3:+.3f}) -> "
                  f"({a1:+.3f}, {a2:+.3f}, {a3:+.3f})  "
                  f"|free|={mag_free:.3f} |aim|={mag_aim:.3f}{tag}")
