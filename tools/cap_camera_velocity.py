"""Live-tune the camera yaw-velocity accumulator at 0x0106DEF8.

Background
==========
The game stores a per-frame angular-velocity accumulator at
    0x0106DEF8  (F8)   — magnitude and sign of camera yaw speed in radians
    0x0106DEFC  (FC)   — per-frame delta (≈ F8 / 60)

When you hold the right stick, F8 ramps UP over ~0.87 s and saturates at
5π/3 ≈ 5.236. This is what makes the camera "build up speed the longer
you push" and feel compound-accelerated on repeated presses. When the
stick is released, F8 decays back to 0 over another ~0.87 s — that's
the "coast / drift" after release.

This tool hammers three tuning knobs on F8 live via PINE:

  1. CAP          max |F8| magnitude. Lower = lower max camera speed.
                  Vanilla saturation is ~5.236.
  2. GROWTH_RATE  fraction of the game's per-frame growth increments
                  we keep. 1.0 = natural, 0.3 = only 30% of each
                  increment lands (70% dampened). Lower = slower ramp-up.
  3. SNAP_BELOW   once F8 is decaying (magnitude shrinking) AND its
                  value drops below this, we snap it to 0 immediately.
                  Higher = camera stops sooner after stick release.

Presets (user testing, 2026-04-23)
==================================
    v1:  cap=1.5  growth=1.0 (none)  snap=0.3
         First sweet spot. Natural ramp to 1.5, light stop.
    v2:  cap=2.0  growth=0.3         snap=1.0     <-- default
         Refined. Higher max speed but ramp is dampened so it doesn't
         build up as fast. Aggressive stop on release (snap at 1.0
         kills the drift tail).

Usage
=====
    py cap_camera_velocity.py                  # v2 preset (default)
    py cap_camera_velocity.py --preset v1
    py cap_camera_velocity.py --cap 2.5 --growth 0.4 --snap-below 0.8
    py cap_camera_velocity.py --off

Ctrl+C to stop.

Implementation notes
====================
Hammer rate ≈ 125 Hz (8 ms per iteration) — well above the game's ~60 Hz
write rate, so our clamps/dampens/snaps land reliably.

Growth dampening takes the fresh game-written value and replaces it
with `prev_written + delta * GROWTH_RATE`, where `prev_written` is the
last value WE wrote. This is important — if we compared against the
game's previous value we'd double-apply dampening.

Decay detection compares magnitude-drop against the raw read vs. what
we last wrote, so passive decay triggers the snap but our own dampening
does not.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

F8_ADDR = 0x0106DEF8
HAMMER_INTERVAL = 0.008

PRESETS: dict[str, dict] = {
    "v1": {"cap": 1.5, "growth": 1.0, "snap_below": 0.3},
    "v2": {"cap": 2.0, "growth": 0.3, "snap_below": 1.0},
}


def f32_to_u32(f: float) -> int:
    return struct.unpack('<I', struct.pack('<f', f))[0]


def u32_to_f32(u: int) -> float:
    return struct.unpack('<f', struct.pack('<I', u))[0]


def run(cap: float, growth_rate: float, snap_below: float) -> None:
    cap_pos_word = f32_to_u32(+cap)
    cap_neg_word = f32_to_u32(-cap)
    zero_word = f32_to_u32(0.0)

    print(f'[*] cap          = {cap:.3f}    (max |F8|)')
    print(f'[*] growth rate  = {growth_rate:.3f}x  (1.0 = natural ramp, <1 = dampened)')
    print(f'[*] snap below   = {snap_below:.3f}    (decay + below this → 0)')
    print('[*] Ctrl+C to stop.')
    print()

    caps = dampens = snaps = 0
    t_start = time.time()
    try:
        with PineClient() as pc:
            prev_written = 0.0
            while True:
                v = pc.read_u32(F8_ADDR)
                cur = u32_to_f32(v)
                abs_cur = abs(cur)
                abs_prev = abs(prev_written)
                new = cur

                # 1. Growth dampening — only when same-sign growth
                if growth_rate < 1.0 and abs_cur > abs_prev and (
                        cur * prev_written >= 0 or prev_written == 0):
                    delta = cur - prev_written
                    new = prev_written + delta * growth_rate
                    dampens += 1

                # 2. Cap
                if new > cap:
                    new = cap
                    caps += 1
                elif new < -cap:
                    new = -cap
                    caps += 1

                # 3. Snap decay tail
                if snap_below > 0 and 0 < abs(new) < snap_below and abs(new) < abs_prev - 1e-4:
                    new = 0.0
                    snaps += 1

                if new != cur:
                    pc.write_u32(F8_ADDR, f32_to_u32(new))
                prev_written = new

                time.sleep(HAMMER_INTERVAL)
    except KeyboardInterrupt:
        elapsed = time.time() - t_start
        print()
        print(f'[*] Stopped after {elapsed:.1f}s.')
        print(f'    caps:    {caps:>6}')
        print(f'    dampens: {dampens:>6}')
        print(f'    snaps:   {snaps:>6}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--preset', choices=list(PRESETS.keys()),
                    help="Use a named preset (v1 or v2). Overrides individual settings.")
    ap.add_argument('--cap', type=float, default=None,
                    help="Max |F8|. Vanilla ~5.236, v1 preset 1.5, v2 preset 2.0.")
    ap.add_argument('--growth', type=float, default=None,
                    help="Growth-rate multiplier 0..1. 1.0 = natural, 0.3 = 70%% dampened.")
    ap.add_argument('--snap-below', type=float, default=None,
                    help="Snap F8 to 0 when decaying and |F8| drops below this.")
    ap.add_argument('--off', action='store_true',
                    help="Don't run; exit immediately.")
    args = ap.parse_args()

    if args.off:
        print('[*] --off: no hammer. Exiting.')
        return

    # Default to v2 preset; explicit --cap/--growth/--snap-below override.
    preset_name = args.preset or 'v2'
    cfg = dict(PRESETS[preset_name])
    if args.cap is not None: cfg['cap'] = args.cap
    if args.growth is not None: cfg['growth'] = args.growth
    if args.snap_below is not None: cfg['snap_below'] = args.snap_below

    print(f'[*] Preset: {preset_name}')
    run(cfg['cap'], cfg['growth'], cfg['snap_below'])


if __name__ == '__main__':
    main()
