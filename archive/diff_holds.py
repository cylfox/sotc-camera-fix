"""Diff two parallel-scan captures to find offsets whose STABLE value differs
between the two scenarios.

For each offset, take the median of all snapshots in each capture (robust to
occasional transient values). An offset is "pitch-direction-sensitive" if its
median differs across up-hold vs down-hold AND both medians are stable.
"""

import json
import struct
import sys
from pathlib import Path

SCEN_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def f32(raw: int) -> float:
    return struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]


def classify(raw: int) -> str:
    if raw == 0:
        return "zero"
    if 0x00100000 <= raw <= 0x02000000:
        return "ptr"
    exp = (raw >> 23) & 0xFF
    fv = f32(raw)
    if 0x68 <= exp <= 0x96 and -1e6 < fv < 1e6:
        return "f32"
    return "u32"


def per_offset_samples(snapshots, offset, n_bytes):
    return [struct.unpack("<I", snap[offset:offset + 4])[0] for _, snap in snapshots]


def main() -> None:
    a_name = sys.argv[1] if len(sys.argv) > 1 else "pitch_hold_up"
    b_name = sys.argv[2] if len(sys.argv) > 2 else "pitch_hold_down"

    a = json.load(open(SCEN_DIR / f"pscan_{a_name}.json"))
    b = json.load(open(SCEN_DIR / f"pscan_{b_name}.json"))
    base = a["base"]; size = a["size"]
    assert a["base"] == b["base"] and a["size"] == b["size"]

    a_snaps = [(s["t"], bytes.fromhex(s["hex"])) for s in a["snapshots"]]
    b_snaps = [(s["t"], bytes.fromhex(s["hex"])) for s in b["snapshots"]]

    n_words = size // 4
    hits = []

    for i in range(n_words):
        off = 4 * i
        a_vals = [struct.unpack("<I", s[off:off+4])[0] for _, s in a_snaps]
        b_vals = [struct.unpack("<I", s[off:off+4])[0] for _, s in b_snaps]
        a_uniq = len(set(a_vals))
        b_uniq = len(set(b_vals))
        # Want stable-in-each-scenario, different-between
        a_val = sorted(a_vals)[len(a_vals)//2]
        b_val = sorted(b_vals)[len(b_vals)//2]
        if a_val != b_val:
            hits.append({
                "offset": off,
                "a_val": a_val, "b_val": b_val,
                "a_uniq": a_uniq, "b_uniq": b_uniq,
                "delta_float": abs(f32(a_val) - f32(b_val)),
            })

    print(f"Total offsets with differing median: {len(hits)} / {n_words}")

    # Filter: floats, both-stable (a_uniq==1 and b_uniq==1), non-zero deltas
    stable_float_hits = [h for h in hits
                         if classify(h["a_val"]) == "f32"
                         and h["a_uniq"] == 1 and h["b_uniq"] == 1]
    print(f"Stable-in-both, float type: {len(stable_float_hits)}")
    print()
    print("Top 50 pitch-direction-sensitive floats (sorted by |up - down|):")
    print(f"{'addr':>10}  {'offset':>8}  {'up_val':>12}  {'down_val':>12}  {'|delta|':>10}")
    for h in sorted(stable_float_hits, key=lambda x: -x["delta_float"])[:50]:
        addr = base + h["offset"]
        print(f"  0x{addr:08X}  +0x{h['offset']:05X}  "
              f"{f32(h['a_val']):+12.4g}  {f32(h['b_val']):+12.4g}  "
              f"{h['delta_float']:10.4g}")

    # Also dump non-zero deltas that aren't floats (could be packed or int fields)
    other_hits = [h for h in hits
                  if classify(h["a_val"]) != "f32"
                  and h["a_uniq"] == 1 and h["b_uniq"] == 1
                  and h["a_val"] != 0 and h["b_val"] != 0]
    if other_hits:
        print()
        print(f"Non-float stable differing offsets (top 20):")
        for h in sorted(other_hits, key=lambda x: -abs(x["a_val"] - x["b_val"]))[:20]:
            addr = base + h["offset"]
            print(f"  0x{addr:08X}  +0x{h['offset']:05X}  "
                  f"a=0x{h['a_val']:08X}  b=0x{h['b_val']:08X}  "
                  f"diff={abs(h['a_val']-h['b_val'])}  ({classify(h['a_val'])})")


if __name__ == "__main__":
    main()
