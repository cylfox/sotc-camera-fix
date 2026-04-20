"""Analyze a parallel-scan capture: find offsets that changed across snapshots."""

import json
import struct
import sys
from pathlib import Path

SCEN_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def as_f32(raw: int) -> float:
    return struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]


def classify_type(raw: int) -> str:
    if raw == 0:
        return "zero"
    if 0x00100000 <= raw <= 0x02000000:
        return "ptr"
    exp = (raw >> 23) & 0xFF
    f = as_f32(raw)
    if 0x68 <= exp <= 0x96 and -1e6 < f < 1e6:
        return "f32"
    if raw < 0x10000:
        return "small_int"
    return "u32"


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "rotate"
    path = SCEN_DIR / f"pscan_{name}.json"
    with path.open() as f:
        data = json.load(f)
    base = data["base"]
    size = data["size"]
    snaps = [(s["t"], bytes.fromhex(s["hex"])) for s in data["snapshots"]]
    n = len(snaps)
    print(f"Scan 0x{base:08X}..+0x{size:X}, {n} snapshots over {data['duration']}s")
    print()

    # For each 4-byte word offset, list the sequence of u32 values
    n_words = size // 4
    hits: list = []
    for i in range(n_words):
        off = 4 * i
        vals = []
        for _, s in snaps:
            v = struct.unpack("<I", s[off:off + 4])[0]
            vals.append(v)
        uniq = set(vals)
        if len(uniq) > 1:
            hits.append((off, vals))

    print(f"Offsets that changed across snapshots: {len(hits)} / {n_words}")

    # Classify: float hits are most interesting for camera orientation/position
    float_hits = []
    for off, vals in hits:
        kind = classify_type(vals[0])
        if kind == "f32":
            fvs = [as_f32(v) for v in vals]
            frange = max(fvs) - min(fvs)
            float_hits.append((off, vals, fvs, frange))

    float_hits.sort(key=lambda x: -x[3])
    print(f"Float-like hits: {len(float_hits)}")
    print()
    print(f"Top 40 by float-range:")
    print(f"{'addr':>10}  {'off':>8}  {'range':>12}  {'first':>12}  {'last':>12}  {'mid':>12}")
    for off, vals, fvs, frange in float_hits[:40]:
        addr = base + off
        print(f"  0x{addr:08X}  +0x{off:05X}  {frange:12.4g}  "
              f"{fvs[0]:+12.4g}  {fvs[-1]:+12.4g}  {fvs[len(fvs)//2]:+12.4g}")

    # Detect clustered triples: 3 consecutive float offsets that all changed
    # (likely vec3 of position or direction)
    print()
    print("Consecutive float triples (possible vec3s):")
    float_offs = {off for off, _, _, _ in float_hits}
    triples_found = []
    for off in sorted(float_offs):
        if (off + 4) in float_offs and (off + 8) in float_offs:
            if (off - 4) not in float_offs:  # start of run
                triples_found.append(off)
    print(f"  count: {len(triples_found)}")
    for off in triples_found[:20]:
        addr = base + off
        # Get triple values across time
        print(f"  0x{addr:08X} (+0x{off:05X})")
        for i, (off1, _, fv, _) in enumerate([h for h in float_hits if h[0] in (off, off+4, off+8)][:3]):
            print(f"    comp {i}: range {fv[0]:+.4g} -> {fv[-1]:+.4g}")


if __name__ == "__main__":
    main()
