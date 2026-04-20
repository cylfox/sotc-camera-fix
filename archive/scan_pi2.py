"""Scan memory for the float PI/2 (0x3FC90FDB) across key heap regions."""
import sys, struct, time
sys.path.insert(0, r'C:\Users\Marcos\sotc')
from pine_client import PineClient

TARGET = 0x3FC90FDB  # PI/2 exactly
NEAR = 0x3FC90FDC    # tolerate +/- 1 ULP

def main():
    regions = [
        (0x00100000, 0x100000),  # low mem (includes pad)
        (0x01000000, 0x100000),  # 16MB of heap
        (0x01400000, 0x100000),  # more heap (external pointer area)
        (0x01C00000, 0x80000),   # camera region
    ]
    print(f"Scanning for PI/2 = 0x{TARGET:08X} (and +/-1 ULP)")
    hits = []
    with PineClient() as pc:
        for base, size in regions:
            print(f"  scanning 0x{base:08X}..+{size:X}...", end="", flush=True)
            t0 = time.monotonic()
            # Use read_bytes (each chunk via read_u64) — slow but thorough for small scan
            # For speed, chunk-scan 256KB at a time
            addr = base
            end = base + size
            count = 0
            while addr < end:
                chunk_size = min(0x8000, end - addr)  # 32KB at a time
                chunk = pc.read_bytes(addr, chunk_size)
                for off in range(0, chunk_size, 4):
                    v = struct.unpack_from('<I', chunk, off)[0]
                    if v == TARGET or v == (TARGET - 1) or v == (TARGET + 1):
                        hits.append(addr + off)
                        count += 1
                addr += chunk_size
            dt = time.monotonic() - t0
            print(f" {count} hits, {dt:.1f}s")
    print(f"\nTotal hits: {len(hits)}")
    for h in hits[:50]:
        print(f"  0x{h:08X}")

if __name__ == "__main__":
    main()
