"""Check specific addresses in all stable snapshots."""
import json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "archive" / "scenarios"

ADDRS = [
    0x0106E7C0, 0x0106E7C4, 0x0106E7C8,  # camera pose forward
    0x0106C230, 0x0106C234, 0x0106C238,  # direction buffer L1
]

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

for fn in ["stable_aimcam_free.json", "stable_aimcam_aim.json", "stable_aimcam_aim2.json"]:
    with (OUT / fn).open() as f:
        d = json.load(f)
    print(f"\n=== {fn} ({len(d)} stable offsets) ===")
    for a in ADDRS:
        # JSON keys come from `hex(key)` which produces lowercase '0x106e7c0'
        key_variants = [hex(a), hex(a).lower(), hex(a).upper(), f"0x{a:08x}", f"0x{a:08X}"]
        found = None
        for k in key_variants:
            if k in d:
                found = d[k]
                break
        if found is not None:
            print(f"  0x{a:08X}  0x{found:08X}  ({asf(found):+.4f})  [key={k}]")
        else:
            # Show a sample of actual keys near this address
            nearby = [k for k in d.keys() if f"{a >> 12:05x}" in k]
            nearby = sorted(nearby)[:3]
            print(f"  0x{a:08X}  NOT FOUND.  nearby keys in JSON: {nearby}")
