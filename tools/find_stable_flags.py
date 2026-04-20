"""Find memory addresses that hold a STABLE integer/small-value in free-roam
and a DIFFERENT STABLE value in aim, by polling multiple samples in each state
and keeping only locations where the value didn't change within the state.

Flow:
  1. User in free-roam, `py find_stable_flags.py free` -> takes 20 samples over 2s
  2. User in aim, `py find_stable_flags.py aim` -> 20 samples over 2s
  3. `py find_stable_flags.py diff` -> reports addresses that were:
     - stable in free-roam (single value)
     - stable in aim (single value)
     - different between the two
"""
import argparse, json, os, struct, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

OUT_DIR = Path(__file__).resolve().parent.parent / "archive" / "scenarios"

REGIONS = [
    # Entity regions (Wander state likely lives here)
    (0x01301000, 0x2000, "entity A"),
    (0x0106A000, 0x4000, "camera config / input state"),
    (0x01C18000, 0x2000, "live camera controller"),
    (0x0106E000, 0x1000, "camera pose"),
]

N_SAMPLES = 20
SLEEP_BETWEEN = 0.1


def snapshot_stable(label):
    """Take N_SAMPLES snapshots, save the SET of values seen at each offset."""
    print(f"[*] Taking {N_SAMPLES} snapshots for state '{label}'...")
    sample_sets = {}  # key = (base, offset) -> set of values
    with PineClient() as pc:
        for i in range(N_SAMPLES):
            for base, size, desc in REGIONS:
                buf = pc.read_bytes(base, size)
                for off in range(0, size, 4):
                    v = struct.unpack_from('<I', buf, off)[0]
                    key = base + off
                    sample_sets.setdefault(key, set()).add(v)
            if i < N_SAMPLES - 1:
                time.sleep(SLEEP_BETWEEN)
            print(f"  sample {i+1}/{N_SAMPLES}", end='\r', flush=True)
    print()
    # Keep only stable offsets (single value across all samples)
    stable = {k: next(iter(s)) for k, s in sample_sets.items() if len(s) == 1}
    print(f"[*] {len(stable)} stable offsets found (out of {len(sample_sets)} total)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"stable_{label}.json"
    with path.open('w') as f:
        json.dump({hex(k): v for k, v in stable.items()}, f)
    print(f"    saved {path}")


def diff_stable():
    """Report addresses that are stable-and-different between free and aim."""
    path_f = OUT_DIR / "stable_free.json"
    path_a = OUT_DIR / "stable_aim.json"
    if not path_f.exists() or not path_a.exists():
        print("[!] Need stable_free.json AND stable_aim.json")
        return
    with path_f.open() as f:
        sf = json.load(f)
    with path_a.open() as f:
        sa = json.load(f)
    # Both stable AND values differ
    candidates = []
    for k, vf in sf.items():
        if k in sa and sa[k] != vf:
            candidates.append((int(k, 16), vf, sa[k]))
    print(f"[*] {len(candidates)} addresses stable in both states with DIFFERENT values:")
    # Sort by smallness-of-values (prefer clean flags)
    def score(item):
        _, vf, va = item
        # Prefer small integers
        max_val = max(vf, va) if vf and va else max(vf or 0, va or 0)
        return max_val
    candidates.sort(key=score)
    for a, vf, va in candidates[:200]:
        fv = struct.unpack('<f', struct.pack('<I', vf))[0]
        av = struct.unpack('<f', struct.pack('<I', va))[0]
        # Check if small integer
        hint = ""
        if vf < 0x10000 and va < 0x10000:
            hint = " [small int]"
        elif (vf & 0xFF000000) == 0 and (va & 0xFF000000) == 0:
            hint = " (low addr / small)"
        print(f"  0x{a:08X}  free=0x{vf:08X}  aim=0x{va:08X}   "
              f"(as float: {fv:+.3f} / {av:+.3f}){hint}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label_or_diff")
    args = ap.parse_args()
    if args.label_or_diff == "diff":
        diff_stable()
    else:
        snapshot_stable(args.label_or_diff)


if __name__ == "__main__":
    main()
