"""Intersect two cutscene snapshots vs one gameplay snapshot.

A letterbox alpha (or height) should be:
  - the SAME value in both bars snapshots (it's bar-state, not cutscene-
    specific animation),
  - DIFFERENT in the nobars snapshot.

Cutscene-only state that differs between the two cutscenes (character
poses, scripted positions, animation timers) gets filtered out by
requiring bars1 == bars2.

Usage:
  py tools/intersect_letterbox.py <bars1> <bars2> <nobars>
"""
import os
import struct
import sys

SNAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snaps")


def load(label):
    bin_path = os.path.join(SNAPS_DIR, f"{label}.bin")
    meta_path = bin_path + ".meta"
    with open(bin_path, "rb") as f:
        data = f.read()
    regions = []
    with open(meta_path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(maxsplit=2)
            if len(parts) < 2:
                continue
            base = int(parts[0], 16)
            size = int(parts[1], 16)
            desc = parts[2] if len(parts) > 2 else ""
            regions.append((base, size, desc))
    offsets = {}
    cursor = 0
    for base, size, _ in regions:
        offsets[base] = (cursor, size)
        cursor += size
    return data, regions, offsets


def f32(buf, idx):
    return struct.unpack_from("<f", buf, idx)[0]


def u32(buf, idx):
    return struct.unpack_from("<I", buf, idx)[0]


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: intersect_letterbox.py <bars1> <bars2> <nobars>")
    a_label, b_label, c_label = sys.argv[1], sys.argv[2], sys.argv[3]
    a_data, a_regions, a_offs = load(a_label)
    b_data, b_regions, _ = load(b_label)
    c_data, c_regions, _ = load(c_label)

    if [(b, s) for b, s, _ in a_regions] != [(b, s) for b, s, _ in b_regions]:
        sys.exit("region layout mismatch a vs b")
    if [(b, s) for b, s, _ in a_regions] != [(b, s) for b, s, _ in c_regions]:
        sys.exit("region layout mismatch a vs c")

    cands_aon = []   # bars=1 in both, nobars=0
    cands_aoff = []  # bars=0 in both, nobars=1
    cands_swing = []  # plausible swing not at saturation

    for base, size, desc in a_regions:
        bo, _ = a_offs[base]
        for off in range(0, size, 4):
            i = bo + off
            ua = u32(a_data, i)
            ub = u32(b_data, i)
            uc = u32(c_data, i)
            # Require bars1 == bars2 (consistent bar-state)
            if ua != ub:
                continue
            # Require change vs nobars
            if ua == uc:
                continue
            fa = f32(a_data, i)
            fc = f32(c_data, i)
            if any(v != v for v in (fa, fc)):
                continue
            if any(abs(v) > 5.0 for v in (fa, fc)):
                continue
            addr = base + off
            if 0.7 <= fa <= 1.3 and abs(fc) <= 0.05:
                cands_aon.append((addr, fa, fc, desc))
            elif 0.7 <= fc <= 1.3 and abs(fa) <= 0.05:
                cands_aoff.append((addr, fa, fc, desc))
            elif 0.0 <= fa <= 1.5 and 0.0 <= fc <= 1.5 and abs(fa - fc) >= 0.1:
                cands_swing.append((addr, fa, fc, desc))

    print(f"[*] bars=1, nobars=0 (canonical alpha pattern, consistent across cutscenes): {len(cands_aon)}")
    for addr, fa, fc, desc in cands_aon:
        print(f"  0x{addr:08X}  bars={fa:+.4f}  nobars={fc:+.4f}  [{desc}]")
    print()
    print(f"[*] bars=0, nobars=1 (inverted, e.g., is_gameplay_active): {len(cands_aoff)}")
    for addr, fa, fc, desc in cands_aoff:
        print(f"  0x{addr:08X}  bars={fa:+.4f}  nobars={fc:+.4f}  [{desc}]")
    print()
    print(f"[*] In-range swing (non-saturated, possible height/position): {len(cands_swing)}")
    for addr, fa, fc, desc in cands_swing[:30]:
        print(f"  0x{addr:08X}  bars={fa:+.4f}  nobars={fc:+.4f}  [{desc}]")


if __name__ == "__main__":
    main()
