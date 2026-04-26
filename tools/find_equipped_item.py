"""Find the equipped-item indicator by diff-scanning memory across equip states.

The Ancient Sword button-swap patch needs to fire ONLY when the sword is out,
so we need a memory address whose value tells us what's equipped. This tool
finds it by poll-and-diff: cycle through items, capture memory per state, then
report addresses that are stable within each state and differ across states.

Usage (capture/analyse split)
=============================
  PCSX2 + PINE running. Wander on foot, IDLE, no buttons/sticks held during
  each capture. Between captures, equip the next item and release all inputs.

    py find_equipped_item.py capture sword    # sword equipped
    py find_equipped_item.py capture bow      # swap to bow
    py find_equipped_item.py capture hand     # swap to hand
    py find_equipped_item.py capture sword    # back to sword (consistency check)
    py find_equipped_item.py analyse          # reports candidates

Captures are saved as JSON under `archive/scenarios/equipped_<label>[_N].json`.
Re-using a label (e.g. "sword" twice) appends a _2, _3, ... suffix and the
analyse step cross-checks that same-label captures agree.

Reset between runs:
    py find_equipped_item.py reset

Candidate rules
===============
A byte offset is a "candidate" if ALL of:
  - single stable value across all samples within every capture
  - agrees across all captures with the same label
  - differs between at least two distinct labels

Sort is ascending by max value, preferring enum-like bytes (0..few).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

# Default scan regions: known game-state flag zone + a small pose slice.
DEFAULT_REGIONS = [
    (0x0106A000, 0x4000, "camera config / input / game state"),
    (0x0106E000, 0x2000, "camera pose / adjacent state"),
]

N_SAMPLES = 5
SAMPLE_INTERVAL = 0.1

OUT_DIR = Path(__file__).resolve().parent.parent / "archive" / "scenarios"


def capture_one(regions, label: str) -> Path:
    """Take N_SAMPLES snapshots; save byte values that were stable across all
    samples. Assigns a unique filename if the label was already used."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Find next free index for this label
    idx = 1
    while True:
        suffix = "" if idx == 1 else f"_{idx}"
        path = OUT_DIR / f"equipped_{label}{suffix}.json"
        if not path.exists():
            break
        idx += 1

    total = sum(sz for _, sz, _ in regions)
    print(f"[*] Capturing '{label}' (will save as {path.name})")
    print(f"    {N_SAMPLES} samples @ {SAMPLE_INTERVAL:.2f}s, scanning {total} bytes total")
    per_addr: dict[int, set[int]] = defaultdict(set)
    with PineClient() as pc:
        for i in range(N_SAMPLES):
            for base, size, _ in regions:
                buf = pc.read_bytes(base, size)
                for off, b in enumerate(buf):
                    per_addr[base + off].add(b)
            if i < N_SAMPLES - 1:
                time.sleep(SAMPLE_INTERVAL)
            print(f"    sample {i+1}/{N_SAMPLES}", end='\r', flush=True)
    print()
    stable = {a: next(iter(s)) for a, s in per_addr.items() if len(s) == 1}
    print(f"[*] {len(stable)} stable bytes / {len(per_addr)} total")
    with path.open("w") as f:
        json.dump({"label": label, "stable": {hex(a): v for a, v in stable.items()}}, f)
    print(f"    saved {path}")
    return path


def _label_from_filename(name: str) -> str:
    # equipped_<label>[_N].json
    stem = name[len("equipped_"):-len(".json")]
    # Trim trailing _<digit>+
    import re
    m = re.match(r"^(.*?)(?:_(\d+))?$", stem)
    return m.group(1) if m else stem


def analyse() -> None:
    if not OUT_DIR.exists():
        print(f"[!] No captures in {OUT_DIR}")
        return
    paths = sorted(OUT_DIR.glob("equipped_*.json"))
    if not paths:
        print(f"[!] No captures in {OUT_DIR}")
        return

    captures: list[tuple[str, dict[int, int]]] = []
    for p in paths:
        with p.open() as f:
            data = json.load(f)
        label = data.get("label") or _label_from_filename(p.name)
        stable = {int(k, 16): v for k, v in data["stable"].items()}
        captures.append((label, stable))
        print(f"[*] Loaded {p.name}: label='{label}', {len(stable)} stable bytes")

    if len(captures) < 2:
        print("[!] Need at least 2 captures with different labels.")
        return

    # Common addresses = intersection of stable keys across every capture
    common = set(captures[0][1].keys())
    for _, cap in captures[1:]:
        common &= cap.keys()
    print(f"\n[*] {len(common)} addresses stable in every capture.")

    # Group captures by label for cross-capture same-label consistency check
    by_label: dict[str, list[dict[int, int]]] = defaultdict(list)
    for label, cap in captures:
        by_label[label].append(cap)

    candidates = []
    for addr in common:
        per_label_value: dict[str, int] = {}
        consistent = True
        for label, caps in by_label.items():
            vals = {cap[addr] for cap in caps}
            if len(vals) != 1:
                consistent = False
                break
            per_label_value[label] = next(iter(vals))
        if not consistent:
            continue
        distinct = set(per_label_value.values())
        if len(distinct) < 2:
            continue
        candidates.append((addr, per_label_value, distinct))

    print(f"[*] {len(candidates)} addresses differ across labels AND are consistent within each label.")

    # Score: prefer small values (enum-like), then more distinct values
    def score(item):
        _, per_label, distinct = item
        return (max(per_label.values()), -len(distinct))
    candidates.sort(key=score)

    if not candidates:
        print("\n[!] No candidates. Possibilities:")
        print("    - scan range too narrow (try --extra-region in capture mode)")
        print("    - state didn't actually change between captures")
        print("    - noise in captures (repeat with same label twice)")
        return

    # Print top 40
    labels = list(by_label.keys())
    header = "  ".join(f"{L:>10}" for L in labels)
    print(f"\n  {'addr':>10}   {header}   distinct")
    for addr, per_label, distinct in candidates[:40]:
        cols = "  ".join(f"{per_label[L]:>10d}" for L in labels)
        print(f"  0x{addr:08X}   {cols}   {len(distinct)}")

    top_addr, _, _ = candidates[0]
    print(f"\n[*] Top candidate: 0x{top_addr:08X}")
    print(f"    Live-watch:   py pine_client.py dump 0x{top_addr & ~3:08X} 4")
    print(f"    Live-watch:   py pine_client.py poll 0x{top_addr & ~3:08X} 1 --duration 5 --hz 10")


def reset() -> None:
    if not OUT_DIR.exists():
        print(f"[*] Nothing to reset ({OUT_DIR} doesn't exist).")
        return
    removed = 0
    for p in OUT_DIR.glob("equipped_*.json"):
        p.unlink()
        removed += 1
    print(f"[*] Removed {removed} capture file(s) from {OUT_DIR}.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="Capture current state with a label")
    cap.add_argument("label")
    cap.add_argument("--extra-region", nargs=2, action="append", default=[],
                     metavar=("BASE", "SIZE"),
                     help="Additional (base, size). Hex OK. Can repeat.")

    sub.add_parser("analyse", help="Report candidates from saved captures")
    sub.add_parser("analyze", help="Alias for 'analyse'")
    sub.add_parser("reset", help="Delete all saved captures")

    args = ap.parse_args()

    if args.cmd == "capture":
        regions = list(DEFAULT_REGIONS)
        for base_s, size_s in args.extra_region:
            regions.append((int(base_s, 0), int(size_s, 0), "user"))
        print("[*] Scan regions:")
        for base, size, desc in regions:
            print(f"      0x{base:08X} + 0x{size:04X}   [{desc}]")
        capture_one(regions, args.label)
    elif args.cmd in ("analyse", "analyze"):
        analyse()
    elif args.cmd == "reset":
        reset()


if __name__ == "__main__":
    main()
