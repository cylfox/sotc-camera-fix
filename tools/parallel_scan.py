"""Fast parallel-PINE memory scanner.

Uses N simultaneous TCP connections (PINE processes each independently)
to read a memory range ~8x faster than a single connection.

Usage:
    py parallel_scan.py <scenario_name> [--base 0x01C00000] [--size 0x40000]
                                         [--duration 15] [--conn 16]

Each snapshot reads `size` bytes via read_u64 from `base`. Successive
snapshots are recorded with timestamps for later time-series analysis.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "archive" / "scenarios"


def snapshot_worker(host: str, port: int, base: int, start_off: int,
                    n_u64: int, out: bytearray, err_box: list) -> None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10.0)
        s.connect((host, port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        for i in range(n_u64):
            addr = base + start_off + 8 * i
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
            out[start_off + 8 * i:start_off + 8 * i + 8] = body[1:9]
        s.close()
    except Exception as e:
        err_box.append(repr(e))


def take_snapshot(host: str, port: int, base: int, size: int, n_conn: int) -> bytes:
    """Take one full snapshot of `size` bytes at `base`, using n_conn parallel
    connections. Returns a bytes object of length `size`."""
    assert size % 8 == 0, "size must be multiple of 8"
    assert size % n_conn == 0, "size must be divisible by n_conn"

    chunk_bytes = size // n_conn
    assert chunk_bytes % 8 == 0
    chunk_u64 = chunk_bytes // 8

    buf = bytearray(size)
    errs: list = []

    threads = [
        threading.Thread(
            target=snapshot_worker,
            args=(host, port, base, i * chunk_bytes, chunk_u64, buf, errs),
            daemon=True,
        )
        for i in range(n_conn)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errs:
        raise RuntimeError(f"{len(errs)} worker(s) failed: {errs[0]}")
    return bytes(buf)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=28011)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x01C00000)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x40000)  # 256 KB
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--conn", type=int, default=16)
    ap.add_argument("--pre-delay", type=float, default=3.0)
    args = ap.parse_args()

    print(f"[*] Parallel scan '{args.name}': 0x{args.base:08X}..+0x{args.size:X} "
          f"for {args.duration}s with {args.conn} connections")

    if args.pre_delay > 0:
        for i in range(int(args.pre_delay), 0, -1):
            print(f"    refocus PCSX2 and perform the action... starting in {i}")
            time.sleep(1.0)

    t0 = time.monotonic()
    end = t0 + args.duration
    snapshots: list[tuple[float, bytes]] = []

    while time.monotonic() < end:
        t_snap_start = time.monotonic() - t0
        snap = take_snapshot(args.host, args.port, args.base, args.size, args.conn)
        t_snap_end = time.monotonic() - t0
        snapshots.append((t_snap_start, snap))
        print(f"    [{len(snapshots):3d}] t={t_snap_start:5.2f}s "
              f"(took {t_snap_end - t_snap_start:.2f}s)")

    total = time.monotonic() - t0
    print(f"[*] Took {len(snapshots)} snapshots in {total:.1f}s "
          f"(avg {total/len(snapshots):.2f}s per snap)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"pscan_{args.name}.json"
    with out_path.open("w") as f:
        json.dump({
            "base": args.base,
            "size": args.size,
            "duration": args.duration,
            "conn": args.conn,
            "snapshots": [{"t": t, "hex": s.hex()} for t, s in snapshots],
        }, f)
    print(f"[*] Saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
