"""Analyze scenarios/*.json and classify each offset by change behavior.

Produces:
  - scenarios/analysis.json          (full machine-readable)
  - scenarios/analysis_summary.txt   (human-readable table of interesting offsets)
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path

SCEN_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")
SCENARIOS = ["idle", "yaw", "pitch", "walk"]


@dataclass
class WordStats:
    offset: int
    first: int
    last: int
    unique: int          # count of distinct values observed
    changed: bool
    f_min: float
    f_max: float
    f_range: float       # |f_max - f_min|
    looks_like: str      # classification hint

    def to_dict(self):
        return asdict(self)


def classify(raw: int) -> str:
    if raw == 0:
        return "zero"
    if 0x00100000 <= raw <= 0x02000000:
        return "ptr"
    exp = (raw >> 23) & 0xFF
    f = struct.unpack("<f", struct.pack("<I", raw))[0]
    if 0x68 <= exp <= 0x96 and -1e6 < f < 1e6:
        return "float"
    if raw < 0x10000:
        return "small_int"
    return "u32"


def stats_for_scenario(samples: list[list[int]]) -> list[WordStats]:
    if not samples:
        return []
    n_words = len(samples[0])
    out = []
    for i in range(n_words):
        col = [row[i] for row in samples]
        uniq = set(col)
        floats = [struct.unpack("<f", struct.pack("<I", v))[0] for v in col]
        fmin, fmax = min(floats), max(floats)
        out.append(WordStats(
            offset=4 * i,
            first=col[0],
            last=col[-1],
            unique=len(uniq),
            changed=len(uniq) > 1,
            f_min=fmin,
            f_max=fmax,
            f_range=abs(fmax - fmin),
            looks_like=classify(col[0]),
        ))
    return out


def load_scenario(name: str) -> dict:
    with (SCEN_DIR / f"{name}.json").open() as f:
        return json.load(f)


def main() -> None:
    data = {s: load_scenario(s) for s in SCENARIOS}
    base = data["idle"]["base"]
    size = data["idle"]["size"]

    stats = {s: stats_for_scenario(data[s]["samples"]) for s in SCENARIOS}

    n_words = size // 4
    table = []
    for i in range(n_words):
        row = {"offset": 4 * i}
        for s in SCENARIOS:
            ws = stats[s][i]
            row[s] = {
                "changed": ws.changed,
                "unique": ws.unique,
                "f_range": ws.f_range,
                "f_min": ws.f_min,
                "f_max": ws.f_max,
                "first": ws.first,
                "last": ws.last,
                "looks_like": ws.looks_like,
            }
        table.append(row)

    analysis = {
        "base": base,
        "size": size,
        "scenarios": SCENARIOS,
        "table": table,
    }
    out_json = SCEN_DIR / "analysis.json"
    with out_json.open("w") as f:
        json.dump(analysis, f, indent=1)

    # Produce human summary highlighting interesting offsets
    def changed_in(row, s): return row[s]["changed"]
    def float_range(row, s): return row[s]["f_range"]

    # Categorize every offset
    lines = [
        f"Analysis of camera controller struct at 0x{base:08X}, size 0x{size:X}",
        f"Scenarios: {', '.join(SCENARIOS)}",
        "=" * 100,
        "",
    ]

    def type_guess(row):
        # Take whichever scenario's first value is non-zero for type hint
        for s in SCENARIOS:
            if row[s]["first"] != 0:
                return row[s]["looks_like"]
        return "zero"

    # === Category 1: auto-center suspects (walk yes, idle no)
    lines.append("### [AUTO-CENTER SUSPECTS] changed during WALK, not during IDLE")
    lines.append("")
    lines.append(f"{'offset':>8}  {'type':>9}  {'idle':>5}  {'yaw':>5}  {'pitch':>5}  {'walk':>5}  {'walk_range':>12}  {'first':>10}  {'last':>10}")
    hits = []
    for row in table:
        if changed_in(row, "walk") and not changed_in(row, "idle"):
            hits.append(row)
    for row in sorted(hits, key=lambda r: -float_range(r, "walk")):
        lines.append(
            f"  +0x{row['offset']:04X}  {type_guess(row):>9}  "
            f"{'Y' if row['idle']['changed'] else '.':>5}  "
            f"{'Y' if row['yaw']['changed'] else '.':>5}  "
            f"{'Y' if row['pitch']['changed'] else '.':>5}  "
            f"{'Y' if row['walk']['changed'] else '.':>5}  "
            f"{float_range(row, 'walk'):12.4g}  "
            f"0x{row['walk']['first']:08X}  0x{row['walk']['last']:08X}"
        )
    if not hits:
        lines.append("  (none)")
    lines.append("")

    # === Category 2: yaw-only fields
    lines.append("### [YAW USER INPUT] changed during YAW, not during IDLE/WALK")
    lines.append("")
    lines.append(f"{'offset':>8}  {'type':>9}  {'yaw_range':>12}  {'yaw_first':>12}  {'yaw_last':>12}")
    hits = []
    for row in table:
        if changed_in(row, "yaw") and not changed_in(row, "idle") and not changed_in(row, "walk"):
            hits.append(row)
    for row in sorted(hits, key=lambda r: -float_range(r, "yaw")):
        yaw = row["yaw"]
        f_first = struct.unpack("<f", struct.pack("<I", yaw["first"]))[0]
        f_last = struct.unpack("<f", struct.pack("<I", yaw["last"]))[0]
        lines.append(f"  +0x{row['offset']:04X}  {type_guess(row):>9}  {float_range(row, 'yaw'):12.4g}  {f_first:+12.4g}  {f_last:+12.4g}")
    if not hits:
        lines.append("  (none)")
    lines.append("")

    # === Category 3: pitch-only fields
    lines.append("### [PITCH USER INPUT] changed during PITCH, not during IDLE/WALK")
    lines.append("")
    hits = []
    for row in table:
        if changed_in(row, "pitch") and not changed_in(row, "idle") and not changed_in(row, "walk"):
            hits.append(row)
    for row in sorted(hits, key=lambda r: -float_range(r, "pitch")):
        p = row["pitch"]
        f_first = struct.unpack("<f", struct.pack("<I", p["first"]))[0]
        f_last = struct.unpack("<f", struct.pack("<I", p["last"]))[0]
        lines.append(f"  +0x{row['offset']:04X}  {type_guess(row):>9}  {float_range(row, 'pitch'):12.4g}  {f_first:+12.4g}  {f_last:+12.4g}")
    if not hits:
        lines.append("  (none)")
    lines.append("")

    # === Category 4: always-changing (frame counters, downstream outputs)
    lines.append("### [ALWAYS CHANGING] changed in all 4 scenarios (frame counters, transform outputs)")
    lines.append("")
    hits = [row for row in table if all(changed_in(row, s) for s in SCENARIOS)]
    lines.append(f"  count: {len(hits)} offsets")
    for row in hits[:20]:
        lines.append(
            f"  +0x{row['offset']:04X}  {type_guess(row):>9}  "
            f"idle_range={float_range(row, 'idle'):10.4g}  walk_range={float_range(row, 'walk'):10.4g}"
        )
    if len(hits) > 20:
        lines.append(f"  ... ({len(hits) - 20} more)")
    lines.append("")

    # === Category 5: constant in all scenarios (likely layout / pointers)
    lines.append("### [CONSTANT] did not change in any scenario")
    lines.append("")
    hits = [row for row in table if not any(changed_in(row, s) for s in SCENARIOS)]
    lines.append(f"  count: {len(hits)} offsets")
    # only show non-zero constants (zeros are padding)
    non_zero = [r for r in hits if r["idle"]["first"] != 0]
    lines.append(f"  non-zero constants: {len(non_zero)}")
    for row in non_zero[:40]:
        v = row['idle']['first']
        f = struct.unpack("<f", struct.pack("<I", v))[0]
        lines.append(f"  +0x{row['offset']:04X}  {type_guess(row):>9}  0x{v:08X}  ({f:+.6g} as f32)")
    if len(non_zero) > 40:
        lines.append(f"  ... ({len(non_zero) - 40} more non-zero)")
    lines.append("")

    out_txt = SCEN_DIR / "analysis_summary.txt"
    with out_txt.open("w") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))
    print()
    print(f"[*] Saved {out_json}")
    print(f"[*] Saved {out_txt}")


if __name__ == "__main__":
    main()
