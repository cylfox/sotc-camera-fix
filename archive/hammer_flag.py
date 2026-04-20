"""Continuously write a constant value to a memory address to see if
forcing that value changes game behavior.
"""
import argparse, struct, sys, time
from pine_client import PineClient

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", type=lambda s: int(s,0), default=0x0147745C)
    ap.add_argument("--value", type=lambda s: int(s,0), default=0x3F800000)  # float 1.0
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--hz", type=float, default=200.0)
    ap.add_argument("--pre-delay", type=float, default=3.0)
    args = ap.parse_args()

    print(f"Hammer 0x{args.addr:08X} := 0x{args.value:08X} ({struct.unpack('<f', struct.pack('<I', args.value))[0]:+g}) "
          f"for {args.duration}s @ {args.hz} Hz")
    if args.pre_delay > 0:
        for i in range(int(args.pre_delay), 0, -1):
            print(f"    refocus PCSX2 & start pitch test... in {i}")
            time.sleep(1.0)

    interval = 1.0 / args.hz
    end = time.monotonic() + args.duration
    count = 0
    with PineClient() as pc:
        while time.monotonic() < end:
            pc.write_u32(args.addr, args.value)
            count += 1
            time.sleep(interval)
    print(f"Done. Wrote {count} times.")

if __name__ == "__main__":
    sys.exit(main())
