"""Scan EE RAM for a byte-sequence pattern. Generic — used to locate
where the LOD-threshold compare ended up after the boot-time rewriter
moved it out of 0x01197904."""
from __future__ import annotations
import argparse, os, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern_hex", help="byte pattern in hex (no spaces)")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x00100000)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x01F00000)
    ap.add_argument("--chunk", type=lambda s: int(s, 0), default=0x100000)
    args = ap.parse_args()

    pattern = bytes.fromhex(args.pattern_hex)
    print(f"[*] Pattern ({len(pattern)} bytes): {pattern.hex()}")
    print(f"[*] Scan range 0x{args.base:08X}..0x{args.base + args.size:08X}")
    print(f"[*] Chunk size 0x{args.chunk:X}")

    hits = []
    t0 = time.time()
    with PineClient() as pc:
        for cb in range(args.base, args.base + args.size, args.chunk):
            try:
                # Read chunk + pattern-length overlap so a match spanning boundary is still found
                size = min(args.chunk + len(pattern) - 1, args.base + args.size - cb)
                data = pc.read_bytes(cb, size)
            except Exception as e:
                print(f"[!] chunk 0x{cb:08X} failed: {e}")
                continue
            offs = 0
            while True:
                idx = data.find(pattern, offs)
                if idx < 0 or idx >= args.chunk:
                    break
                hits.append(cb + idx)
                offs = idx + 1
            if cb % 0x400000 == 0:
                print(f"  ... scanned up to 0x{cb + args.chunk:08X}")
    elapsed = time.time() - t0
    print(f"\n[*] Done in {elapsed:.1f}s. Found {len(hits)} hit(s):")
    for h in hits[:50]:
        print(f"    0x{h:08X}")
    if len(hits) > 50:
        print(f"    ... {len(hits) - 50} more")


if __name__ == "__main__":
    main()
