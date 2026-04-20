"""Scan EE RAM for `jal <target>` instructions pointing at a given address.

MIPS encoding:
    jal target  ==  0x0C000000 | ((target >> 2) & 0x03FFFFFF)

Uses parallel PINE connections for speed. Prints every match.

Usage:
    py find_jal.py 0x01176AA0
    py find_jal.py 0x01176AA0 --base 0x00100000 --size 0x01F00000 --conn 16
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import threading
import time


def encode_jal(target: int) -> int:
    if target & 3:
        raise ValueError("jal target must be word-aligned")
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def worker_scan(host: str, port: int, base: int, length: int,
                needle: int, hits: list, err_box: list, lock: threading.Lock) -> None:
    """Read `length` bytes starting at `base` via u64 reads, record every
    4-byte-aligned word that matches `needle`."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(30.0)
        s.connect((host, port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        assert length % 8 == 0
        n_u64 = length // 8
        for i in range(n_u64):
            addr = base + 8 * i
            req = struct.pack("<IBI", 9, 0x03, addr)  # read_u64
            s.sendall(req)
            hdr = b""
            while len(hdr) < 4:
                c = s.recv(4 - len(hdr))
                if not c:
                    raise RuntimeError("conn closed mid-header")
                hdr += c
            (rl,) = struct.unpack("<I", hdr)
            body = b""
            want = rl - 4
            while len(body) < want:
                c = s.recv(want - len(body))
                if not c:
                    raise RuntimeError("conn closed mid-body")
                body += c
            # body[0] is status, body[1:9] is u64 little-endian
            lo = struct.unpack("<I", body[1:5])[0]
            hi = struct.unpack("<I", body[5:9])[0]
            if lo == needle:
                with lock:
                    hits.append(addr)
            if hi == needle:
                with lock:
                    hits.append(addr + 4)
        s.close()
    except Exception as e:
        err_box.append(repr(e))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=lambda s: int(s, 0),
                    help="address of function we want to find callers of (e.g. 0x01176AA0)")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x00100000)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x01F00000)
    ap.add_argument("--conn", type=int, default=16)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=28011)
    args = ap.parse_args()

    needle = encode_jal(args.target)
    print(f"[*] Looking for jal 0x{args.target:08X}  (encoded: 0x{needle:08X})")
    print(f"[*] Scan range 0x{args.base:08X}..0x{args.base + args.size:08X}  ({args.size // (1024*1024)} MB)")
    print(f"[*] {args.conn} parallel connections")

    # Align size down to a multiple of (8 * conn) so each worker gets a
    # whole number of u64 ops.
    stride = 8 * args.conn
    size = (args.size // stride) * stride
    per_worker = size // args.conn
    print(f"[*] Effective size 0x{size:X}  ({per_worker // 1024} KB per worker)")

    hits: list[int] = []
    errs: list = []
    lock = threading.Lock()
    t0 = time.monotonic()

    threads = [
        threading.Thread(
            target=worker_scan,
            args=(args.host, args.port, args.base + i * per_worker, per_worker,
                  needle, hits, errs, lock),
            daemon=True,
        )
        for i in range(args.conn)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    dt = time.monotonic() - t0
    if errs:
        print(f"[!] {len(errs)} worker(s) failed: {errs[0]}")
    hits.sort()
    print(f"[*] Done in {dt:.1f}s. Found {len(hits)} hits:")
    for h in hits:
        print(f"    0x{h:08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
