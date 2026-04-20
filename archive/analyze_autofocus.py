"""Split the autofocus capture into phases and identify which fields drive
the late-phase auto-rotation.

Assumptions:
  - Samples 0..N/4:     brief user pan (right stick input)
  - Samples N/4..2N/3:  held steady (no input, pre-trigger)
  - Samples 2N/3..N:    auto-focus rotating the camera back

We look for fields that are CONSTANT in the middle phase but CHANGE in the
late phase. Those are the auto-focus actuators.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

SCEN_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def main() -> None:
    with (SCEN_DIR / "autofocus.json").open() as f:
        data = json.load(f)
    samples = data["samples"]
    base = data["base"]
    n = len(samples)
    n_words = len(samples[0])

    # Phase boundaries
    p1_end = n // 4            # user pan ends
    p2_end = int(n * 0.55)     # rough "settled" window ends, auto-focus starts

    print(f"Total samples: {n}")
    print(f"Phase 1 (user pan)      : 0..{p1_end}")
    print(f"Phase 2 (settled idle)  : {p1_end}..{p2_end}")
    print(f"Phase 3 (auto-rotation) : {p2_end}..{n}")
    print()

    def col(i: int, lo: int, hi: int) -> list[int]:
        return [samples[j][i] for j in range(lo, hi)]

    def as_f32(u: int) -> float:
        return struct.unpack("<f", struct.pack("<I", u))[0]

    hits = []
    for i in range(n_words):
        p2 = col(i, p1_end, p2_end)
        p3 = col(i, p2_end, n)
        p2_uniq = len(set(p2))
        p3_uniq = len(set(p3))
        if p2_uniq <= 1 and p3_uniq > 1:
            p3_floats = [as_f32(v) for v in p3]
            hits.append({
                "offset": 4 * i,
                "p2_value": p2[0] if p2 else 0,
                "p3_first": p3[0],
                "p3_last": p3[-1],
                "p3_uniq": p3_uniq,
                "p3_f_min": min(p3_floats),
                "p3_f_max": max(p3_floats),
                "p3_f_range": abs(max(p3_floats) - min(p3_floats)),
            })

    hits.sort(key=lambda r: -r["p3_f_range"])

    print(f"Fields constant during settled idle, changing during auto-rotation: {len(hits)}")
    print()
    print(f"{'offset':>8}  {'p3_range':>12}  {'p3_first_f':>14}  {'p3_last_f':>14}  {'p2_value':>10}  notes")
    for r in hits[:40]:
        off = r["offset"]
        p2 = r["p2_value"]
        note = ""
        if 0x570 <= off < 0x5D0:
            note = "basis_a field"
        elif 0x5D0 <= off < 0x630:
            note = "basis_b field"
        elif 0x4D0 <= off < 0x4DC:
            note = "target_xyz"
        elif 0x670 <= off < 0x67C:
            note = "output_xyz"
        print(f"  +0x{off:04X}  {r['p3_f_range']:12.5g}  {as_f32(r['p3_first']):+14.4g}  {as_f32(r['p3_last']):+14.4g}  0x{p2:08X}  {note}")

    # Also report basis_a and basis_b specifically — all 0x60 bytes of each
    print()
    print("basis_a (+0x570..+0x5CF) field-by-field, phase 2 vs phase 3:")
    for off in range(0x570, 0x5D0, 4):
        i = off // 4
        p2 = col(i, p1_end, p2_end)
        p3 = col(i, p2_end, n)
        p2_stable = len(set(p2)) <= 1
        p3_change = len(set(p3)) > 1
        p3_first = as_f32(p3[0]) if p3 else 0
        p3_last = as_f32(p3[-1]) if p3 else 0
        marker = " <- trigger" if p2_stable and p3_change else ""
        print(f"  +0x{off:04X}  p2_stable={p2_stable!s:5}  p3_changes={p3_change!s:5}  "
              f"p3: {p3_first:+.4g} -> {p3_last:+.4g}{marker}")

    print()
    print("basis_b (+0x5D0..+0x62F) field-by-field, phase 2 vs phase 3:")
    for off in range(0x5D0, 0x630, 4):
        i = off // 4
        p2 = col(i, p1_end, p2_end)
        p3 = col(i, p2_end, n)
        p2_stable = len(set(p2)) <= 1
        p3_change = len(set(p3)) > 1
        p3_first = as_f32(p3[0]) if p3 else 0
        p3_last = as_f32(p3[-1]) if p3 else 0
        marker = " <- trigger" if p2_stable and p3_change else ""
        print(f"  +0x{off:04X}  p2_stable={p2_stable!s:5}  p3_changes={p3_change!s:5}  "
              f"p3: {p3_first:+.4g} -> {p3_last:+.4g}{marker}")


if __name__ == "__main__":
    main()
