"""Snapshot candidate regions in free-roam vs aim mode, diff to find the
control-mode flag we can use to disable our trampoline in aim states.

Flow:
  1. User in free-roam, hands off stick → snapshot 'free'
  2. User draws bow / raises sword (aim mode), left stick neutral → snapshot 'aim'
  3. Diff → report bytes/words that differ

We target regions known to hold camera/state data:
  - 0x0106C000..+0x2000  (virtual stick / camera input state)
  - 0x0106E000..+0x1000  (camera pose struct region)
  - 0x01C18000..+0x2000  (live camera controller)
  - 0x01301000..+0x2000  (entity Wander area)
  - 0x013000E0..+0x1000  (continuation of entity)
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

OUT_DIR = Path(r'C:\Users\Marcos\sotc\scenarios')

REGIONS = [
    (0x0106C000, 0x2000, "virtual stick / camera input"),
    (0x0106E000, 0x1000, "camera pose region"),
    (0x01C18000, 0x2000, "live camera controller"),
    (0x01301000, 0x2000, "entity Wander region"),
    (0x0106A000, 0x2000, "camera config region"),
]


def snapshot(pc, label):
    print(f"\n[*] Taking snapshot '{label}'...")
    out = {}
    for base, size, desc in REGIONS:
        buf = pc.read_bytes(base, size)
        out[f"{base:08X}"] = {"size": size, "desc": desc, "hex": buf.hex()}
        print(f"    0x{base:08X}..+0x{size:X}  ({desc})")
    return out


def diff_snapshots(a, b, max_hits=200):
    """Report differing 4-byte aligned words between two snapshots."""
    total_diffs = 0
    for key in a:
        if key not in b:
            continue
        size = a[key]["size"]
        desc = a[key]["desc"]
        buf_a = bytes.fromhex(a[key]["hex"])
        buf_b = bytes.fromhex(b[key]["hex"])
        base = int(key, 16)
        region_diffs = []
        for off in range(0, size, 4):
            wa = struct.unpack_from('<I', buf_a, off)[0]
            wb = struct.unpack_from('<I', buf_b, off)[0]
            if wa != wb:
                region_diffs.append((base + off, wa, wb))
        if region_diffs:
            print(f"\n  Region 0x{base:08X} ({desc}): {len(region_diffs)} diffs")
            for addr, wa, wb in region_diffs[:max_hits]:
                # Float interpretation
                fa = struct.unpack('<f', struct.pack('<I', wa))[0]
                fb = struct.unpack('<f', struct.pack('<I', wb))[0]
                fa_s = f"{fa:+.4f}" if -1e6 < fa < 1e6 else "--"
                fb_s = f"{fb:+.4f}" if -1e6 < fb < 1e6 else "--"
                print(f"    0x{addr:08X}  {wa:08X} -> {wb:08X}"
                      f"   ({fa_s} -> {fb_s})")
            if len(region_diffs) > max_hits:
                print(f"    ... {len(region_diffs) - max_hits} more")
            total_diffs += len(region_diffs)
    print(f"\n  TOTAL diffs: {total_diffs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--diff", action="store_true",
                    help="after snapshotting, diff against the other stored snapshot")
    ap.add_argument("--diff-a", default="free")
    ap.add_argument("--diff-b", default="aim")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with PineClient() as pc:
        snap = snapshot(pc, args.label)
        out_path = OUT_DIR / f"modeflag_{args.label}.json"
        with out_path.open('w') as f:
            json.dump(snap, f)
        print(f"\n[*] Saved {out_path}")

    if args.diff:
        path_a = OUT_DIR / f"modeflag_{args.diff_a}.json"
        path_b = OUT_DIR / f"modeflag_{args.diff_b}.json"
        if path_a.exists() and path_b.exists():
            with path_a.open() as f:
                a = json.load(f)
            with path_b.open() as f:
                b = json.load(f)
            print(f"\n[*] Diff {args.diff_a} vs {args.diff_b}:")
            diff_snapshots(a, b)
        else:
            print(f"[!] Both {path_a} and {path_b} must exist for diff.")

if __name__ == "__main__":
    main()
