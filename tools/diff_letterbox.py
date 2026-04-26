"""Diff two snapshots saved by snap_save.py and surface letterbox-alpha
candidates.

Usage:
  py tools/diff_letterbox.py <bars_label> <nobars_label>

Filters for words that:
  - differ between the two snapshots,
  - decode as floats with one snap near 1.0 and the other near 0.0
    (with a tolerance), OR a clean transition in [0, 1.5] range,
  - are not implausibly large (rules out pointers / counters).

Top candidates printed sorted by closeness of the [bars] value to 1.0
and the [nobars] value to 0.0.
"""
import os
import struct
import sys

SNAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snaps")


def load(label):
    bin_path = os.path.join(SNAPS_DIR, f"{label}.bin")
    meta_path = bin_path + ".meta"
    if not os.path.exists(bin_path):
        sys.exit(f"missing {bin_path}")
    if not os.path.exists(meta_path):
        sys.exit(f"missing {meta_path}")
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
    # build address -> offset map
    offsets = {}
    cursor = 0
    for base, size, _ in regions:
        offsets[base] = (cursor, size)
        cursor += size
    if cursor != len(data):
        sys.exit(f"snapshot size mismatch: meta={cursor} bin={len(data)}")
    return data, regions, offsets


def f32(buf, idx):
    return struct.unpack_from("<f", buf, idx)[0]


def u32(buf, idx):
    return struct.unpack_from("<I", buf, idx)[0]


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: diff_letterbox.py <bars_label> <nobars_label>")
    bars_label, nobars_label = sys.argv[1], sys.argv[2]
    bars_data, bars_regions, bars_offs = load(bars_label)
    nobars_data, nobars_regions, _ = load(nobars_label)
    if [(b, s) for b, s, _ in bars_regions] != [(b, s) for b, s, _ in nobars_regions]:
        sys.exit("snapshot region layouts differ; recapture both with same script")

    candidates = []
    for base, size, desc in bars_regions:
        bo, _ = bars_offs[base]
        for off in range(0, size, 4):
            i = bo + off
            ub = u32(bars_data, i)
            un = u32(nobars_data, i)
            if ub == un:
                continue
            fb = f32(bars_data, i)
            fn = f32(nobars_data, i)
            # Skip implausible floats
            if any(v != v for v in (fb, fn)):  # NaN
                continue
            if any(abs(v) > 5.0 for v in (fb, fn)):
                continue
            # Pattern A: bars ~1.0, nobars ~0.0 (or vice versa)
            # Pattern B: any plausible swing in [0, 1.5]
            score = None
            note = ""
            if 0.7 <= fb <= 1.3 and abs(fn) <= 0.05:
                score = abs(fb - 1.0) + abs(fn)
                note = "bars=1, nobars=0"
            elif 0.7 <= fn <= 1.3 and abs(fb) <= 0.05:
                score = abs(fn - 1.0) + abs(fb)
                note = "bars=0, nobars=1 (inverted)"
            elif 0.0 <= fb <= 1.5 and 0.0 <= fn <= 1.5 and abs(fb - fn) >= 0.1:
                score = 1.0 + abs(fb - fn) * 0.1  # weak match, lower priority
                note = "in-range swing"
            else:
                continue
            addr = base + off
            candidates.append((score, addr, fb, fn, desc, note))

    candidates.sort()
    # Per-region histogram
    from collections import Counter
    counts = Counter(c[4] for c in candidates)
    print(f"[*] {len(candidates)} candidates total. Per region:")
    for desc, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {desc}")
    print()
    print(f"  {'addr':<11} {'bars':>10} {'nobars':>10}  pattern")
    print(f"  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*30}")
    show = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    for score, addr, fb, fn, desc, note in candidates[:show]:
        print(f"  0x{addr:08X}  {fb:+.5f}  {fn:+.5f}  {note}  [{desc}]")


if __name__ == "__main__":
    main()
