"""Capture EE memory regions to disk under a label.

Usage:
  py tools/snap_save.py <label>

Captures the regions defined in REGIONS and saves them as
tools/snaps/<label>.bin (raw concatenation in REGIONS order).

Pair with tools/diff_letterbox.py to compare two saved snapshots.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient, MSG_READ64


def bulk_read(pc, base, size, batch=128):
    """Pipelined read: send `batch` READ64 requests, then receive their
    responses. Avoids round-trip latency between adjacent reads.
    Returns `size` bytes starting at `base`. `size` must be multiple of 8.
    """
    assert size % 8 == 0
    sock = pc.sock
    out = bytearray(size)
    n_words = size // 8
    i = 0
    while i < n_words:
        n = min(batch, n_words - i)
        # Build all requests in one buffer, send in one syscall
        req_buf = bytearray()
        for k in range(n):
            addr = base + (i + k) * 8
            req_buf.extend(struct.pack("<IB I", 4 + 1 + 4, MSG_READ64, addr))
        sock.sendall(bytes(req_buf))
        # Read each response: 4-byte length + 1 status + 8 data
        for k in range(n):
            hdr = pc._recv_exact(4)
            (resp_len,) = struct.unpack("<I", hdr)
            rest = pc._recv_exact(resp_len - 4)
            if rest[0] != 0:
                raise RuntimeError(f"PINE read failed at 0x{base + (i+k)*8:08X}")
            out[(i + k) * 8 : (i + k) * 8 + 8] = rest[1:9]
        i += n
    return bytes(out)

REGIONS = [
    # Originally scanned (kept for continuity with earlier snaps)
    (0x01060000, 0x10000, "camera/state page"),       # 64 KB
    (0x01C18000, 0x08000, "live camera controller"),  # 32 KB
    (0x01D00000, 0x10000, "render state (speculative)"),  # 64 KB
    # Expanded coverage — 3.5 MB across likely UI/HUD/render zones
    (0x01000000, 0x60000, "low-mid game data"),       # 384 KB
    (0x010C0000, 0x40000, "above camera state"),      # 256 KB
    (0x01400000, 0x80000, "HUD/UI typical"),          # 512 KB
    (0x01700000, 0x80000, "mid-RAM speculative"),     # 512 KB
    (0x01A00000, 0x80000, "pre-camera-controller"),   # 512 KB
    (0x01D10000, 0x40000, "post render-state"),       # 256 KB
    (0x01F00000, 0x80000, "top of RAM"),              # 512 KB
]

SNAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snaps")


def main():
    if len(sys.argv) < 2:
        print("usage: snap_save.py <label>")
        sys.exit(2)
    label = sys.argv[1]
    os.makedirs(SNAPS_DIR, exist_ok=True)
    out_path = os.path.join(SNAPS_DIR, f"{label}.bin")

    with PineClient() as pc:
        chunks = []
        meta = []
        t0 = time.monotonic()
        for base, size, desc in REGIONS:
            t_region = time.monotonic()
            print(f"  reading 0x{base:08X}+{size:#x} ({desc})...", end=" ", flush=True)
            data = pc.read_bytes(base, size)
            chunks.append(data)
            meta.append((base, size, desc))
            print(f"{time.monotonic() - t_region:.1f}s")
        elapsed = time.monotonic() - t0
        with open(out_path, "wb") as f:
            for d in chunks:
                f.write(d)
        # Write a sidecar manifest so we can diff later without
        # hardcoding the layout.
        with open(out_path + ".meta", "w", encoding="utf-8") as f:
            for base, size, desc in meta:
                f.write(f"{base:08X} {size:08X} {desc}\n")
    total_bytes = sum(s for _, s, _ in REGIONS)
    print(f"[*] saved {total_bytes/1024:.0f} KB to {out_path} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
