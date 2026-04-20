"""Live-assist v2: aggressive hammer-during-window approach.

On free->aim transition: capture matrix, then HAMMER it into 0x0106C230
continuously for OVERRIDE_MS milliseconds with no read-interleaving (to
beat the game's per-frame writes). After the window, stop and let aim
control take over.

This is a closer approximation of how the eventual MIPS trampoline would
behave — once per frame at pad-read time, our write is unconditionally
applied.
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

MODE_FLAG = 0x0106C9FC
# Triple-buffered history chain per session log:
#   0x0106C1B0 <- deepest (written by 0x001B3F28)
#   0x0106C1F0 <- mid (memcpy from 0x0106C1B4)
#   0x0106C230 <- newest, read by renderer
# All three must be pinned so the memcpy chain doesn't reintroduce old values.
BUFFERS   = [0x0106C230, 0x0106C1F0, 0x0106C1B0]

OVERRIDE_MS = 500   # hammer for 500ms after transition

def asf(w): return struct.unpack('<f', struct.pack('<I', w))[0]

def main():
    with PineClient() as pc:
        print(f"[*] Aim-preserve live-assist v2")
        print(f"    Override window: {OVERRIDE_MS}ms (aggressive hammer)")
        print(f"    Ctrl+C to stop.\n")

        last_mode = pc.read_u32(MODE_FLAG)
        saved = (
            pc.read_u32(BUFFERS[0] + 0),
            pc.read_u32(BUFFERS[0] + 4),
            pc.read_u32(BUFFERS[0] + 8),
        )
        transitions = 0
        t_start = time.monotonic()

        try:
            while True:
                mode = pc.read_u32(MODE_FLAG)

                if mode == 1:
                    # Free-roam: keep snapshotting the newest buffer's matrix
                    saved = (
                        pc.read_u32(BUFFERS[0] + 0),
                        pc.read_u32(BUFFERS[0] + 4),
                        pc.read_u32(BUFFERS[0] + 8),
                    )
                elif last_mode == 1 and mode == 0:
                    # TRANSITION free -> aim detected
                    transitions += 1
                    t = time.monotonic() - t_start
                    print(f"[{t:6.2f}s] TRANSITION #{transitions}: hammering full chain "
                          f"({asf(saved[0]):+.3f}, {asf(saved[1]):+.3f}, {asf(saved[2]):+.3f}) "
                          f"for {OVERRIDE_MS}ms")
                    # Aggressive hammer for the override window — all three
                    # buffers, so the memcpy chain keeps propagating OUR value
                    t_end = time.monotonic() + (OVERRIDE_MS / 1000.0)
                    writes = 0
                    while time.monotonic() < t_end:
                        for a in BUFFERS:
                            pc.write_u32(a + 0, saved[0])
                            pc.write_u32(a + 4, saved[1])
                            pc.write_u32(a + 8, saved[2])
                            writes += 3
                    t2 = time.monotonic() - t_start
                    print(f"[{t2:6.2f}s]   ...hammer ended  ({writes} writes)")
                    # After hammer, re-read mode flag in case it changed
                    mode = pc.read_u32(MODE_FLAG)

                last_mode = mode
        except KeyboardInterrupt:
            print(f"\n[*] Stopped. {transitions} transitions handled.")

if __name__ == "__main__":
    main()
