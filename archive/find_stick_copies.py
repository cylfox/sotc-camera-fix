"""Byte-diff two parallel-scan captures to find ALL bytes whose value flips
from ~0xFF to ~0x00 (or vice versa) — i.e., copies of an analog stick byte.
"""

import json
import struct
import sys
from pathlib import Path

SCEN_DIR = Path(r"C:\Users\Marcos\sotc\scenarios")


def main():
    up_name = sys.argv[1]
    down_name = sys.argv[2]
    a = json.load(open(SCEN_DIR / f"pscan_{up_name}.json"))
    b = json.load(open(SCEN_DIR / f"pscan_{down_name}.json"))
    base = a["base"]
    size = a["size"]
    assert a["base"] == b["base"] and a["size"] == b["size"]

    # Take medians (byte-level)
    def median_byte(snaps, off):
        vals = [s[off] for s in snaps]
        return sorted(vals)[len(vals) // 2]

    up_snaps = [bytes.fromhex(s["hex"]) for s in a["snapshots"]]
    down_snaps = [bytes.fromhex(s["hex"]) for s in b["snapshots"]]

    print(f"Scan 0x{base:08X}..+0x{size:X}  ({size} bytes)")
    print(f"up snapshots: {len(up_snaps)}  down snapshots: {len(down_snaps)}")
    print()

    # Candidates: byte that goes from near-0xFF in up to near-0x00 in down
    #             OR near-0x00 in up to near-0xFF in down
    hits = []
    for off in range(size):
        up_v = median_byte(up_snaps, off)
        dn_v = median_byte(down_snaps, off)
        # Full-deflection pattern: |up - dn| >= 0xC0 (very large swing)
        if abs(up_v - dn_v) >= 0xC0:
            # Also require extremes
            if (up_v >= 0xC0 and dn_v <= 0x40) or (up_v <= 0x40 and dn_v >= 0xC0):
                hits.append((off, up_v, dn_v))

    print(f"Full-deflection byte candidates (|up-down| >= 0xC0 AND at extremes): {len(hits)}")
    for off, uv, dv in hits[:50]:
        addr = base + off
        print(f"  0x{addr:08X}  up=0x{uv:02X}  down=0x{dv:02X}  delta={abs(uv-dv)}")

    # Also show moderate-deflection hits
    mod = []
    for off in range(size):
        up_v = median_byte(up_snaps, off)
        dn_v = median_byte(down_snaps, off)
        if 0x40 <= abs(up_v - dn_v) < 0xC0:
            mod.append((off, up_v, dn_v))
    print()
    print(f"Moderate-deflection byte candidates (0x40..0xC0 swing): {len(mod)}")
    for off, uv, dv in sorted(mod, key=lambda x: -abs(x[1]-x[2]))[:30]:
        addr = base + off
        print(f"  0x{addr:08X}  up=0x{uv:02X}  down=0x{dv:02X}  delta={abs(uv-dv)}")


if __name__ == "__main__":
    main()
