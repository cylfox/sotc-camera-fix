# Research: Ancient Sword Button Swap

> Status: RE complete. Ready to ship a configurable pnach. Swap target
> identified at pad-state level; config-table location remains unknown but
> isn't needed for the working solution.

## Goal

In vanilla SotC, the Ancient Sword's two buttons behave as:

- **Attack** (default Square) → one-shot slash animation
- **Action** (default Circle, held) → raise sword to reflect sunlight and
  guide toward a colossus

The user wants these **swapped, but ONLY when the sword is equipped** — so
Attack raises the sword and Action slashes. Other items (bow, fist, menus,
etc.) must retain their normal behavior. The swap must also **respect the
in-game Button Config remap** — SotC lets you rebind each action to any
physical button from Options → Configuración de botones.

## What we discovered about SotC's input pipeline

### The pad pipeline (per frame)

```
   PS2 pad hardware
       │
       │ SIO2 DMA
       ▼
   0x0013A55C/D                ← RAW physical digital u16, active-LOW
                                 bit 0-7 of byte0: Select/L3/R3/Start/D-pad
                                 bit 0-7 of byte1: L2/R2/L1/R1/Triangle/Circle/Cross/Square
       │
       │ memcpy via 0x00114B10 ("pad-copy"), called from
       │ 0x001045B8 ("per-frame pad processor")
       ▼
   0x001DC470                  ← CURRENT pad u16, active-LOW (for controller 1)
   0x001DC474                  ← PREVIOUS pad u16 (last frame)
   0x001DC478                  ← NEWLY RELEASED edge-detect u16 (active-LOW)
   0x001DC47C                  ← NEWLY PRESSED edge-detect u16, active-HIGH
   0x001DC4E8+                 ← same layout for controller 2 (stride 0x78)
       │
       │ consumers (sword handler, menu, game logic) read from here
       ▼
   Downstream game state (AIM flag, sword-raised state, etc.)
```

The per-frame pad processor at `0x001ACC08` (the whole function containing
the v18 camera-fix hook) does the processing. Key operations:

```
0x001ACC6C  jal 0x1045b8                 ; per-frame pad iterate/copy
0x001ACCA0  lbu $v0, 0x104($s2)          ; pad byte 0
0x001ACCA4  lbu $v1, 0x105($s2)          ; pad byte 1
0x001ACCA8  sll $v0, $v0, 8              ; shift hi byte
0x001ACCB0  or  $v0, $v0, $v1            ; combine to u16
0x001ACCB4  xor $a0, $v0, $a0            ; diff against previous
0x001ACCB8  nor $v1, $zero, $v0          ; active-high current
0x001ACCBC  and $v1, $a0, $v1            ; edge: newly-pressed
0x001ACCC0  and $a0, $a0, $v0            ; edge: newly-released
0x001ACCCC  sw  $v0, ($s0)               ; store current (active-low) at s0+0
```

Where `s0 = 0x001DC470 + controller_index * 0x78`.

### The in-game remap layer — NOT FOUND

SotC's Button Config screen lets you reassign each logical action (Saltar,
Acción, Atacar, Agarrar, Ver coloso, Cambiar armas +/-, Centrar cámara,
Zoom de la cámara, Controlar caballo) to any physical button. The config
stores a bitmask per action, and consumers do
`if (pad & action_mask) { ... }`.

Despite extensive scanning (~24 MB of EE RAM covered via before/after
snapshots around an Atacar remap L2→R1, and static `jal` scans for pad
readers), **the config table was not located**. Hypotheses:

- It's stored in a format we didn't search for (byte indices, not u16
  masks; OR packed in a larger struct)
- It lives in the ~8 MB of EE RAM we didn't snapshot
- It's in PS2 scratchpad (not PINE-accessible)
- The masks are hardcoded in each consumer and the remap-screen writes
  patches to the code directly (unusual, but possible for very old games)

Good news: **we don't need it**.

### Key memory addresses

| Address           | What it is                                                               |
| ----------------- | ------------------------------------------------------------------------ |
| `0x0013A55C/D`    | Raw physical digital u16, active-LOW. Hardware-written via SIO2 DMA.     |
| `0x001DC470`      | Current pad u16 (active-LOW) for controller 1. What game consumers read. |
| `0x001DC47C`      | Newly-pressed u16 (active-HIGH) for controller 1.                        |
| `0x0106C441`      | Equipped-item mirror (0=hand, 1=sword, 2=bow). Per-frame updated.        |
| `0x0106C521`      | Equipped-item master (same encoding, NOT overwritten each frame).        |
| `0x0106B484`      | AIM flag mirror (1 when bow-aim or sword-raised active).                 |
| `0x0142BB88`      | Weapon item-equip function (copies 0xC0 bytes from template).            |
| `0x001ACC08`      | Per-frame pad-read function (contains v18 camera-fix hook at `CD44`).    |

### Injection validated

Writing `0xEF` (bit 4 cleared) to `0x0013A55D` continuously at ~19 kHz makes
the game **raise the sword** (as if physical Triangle held, since in the
user's remap Triangle → Acción). This confirms the game processes the raw
pad buffer through its normal remap pipeline, and any bit we inject is
treated as the corresponding physical button press.

## The swap strategy

Since we can't find the config table, we swap at the **processed pad
state** level — `0x001DC470` — the u16 that game consumers read. This is
after the pad processor runs but before per-consumer reads.

**Plan:**

1. Every frame, after `0x001ACC08` processes the pad:
2. Read equipped-item (`0x0106C441`).
3. If `== 1` (sword is equipped):
    - Read pad state at `0x001DC470`
    - Swap two user-configured bits: `ACTION_MASK` and `ATTACK_MASK`
    - Write back
4. Else pass through unchanged.

Because we swap at the processed pad layer but **before** the consumers
apply the user's remap config (remap masks are per-action bitmasks tested
against this pad word), the swap composes correctly:

- User presses physical button mapped to **Attack** → raw bit cleared →
  our patch swaps to Action's bit cleared → consumer sees "Action held" →
  raises sword ✓
- User presses physical button mapped to **Action** → raw bit cleared →
  our patch swaps to Attack's bit cleared → consumer sees "Attack held" →
  slash ✓

**Caveat**: we don't know which physical bit corresponds to each action for
an arbitrary user's remap. The pnach therefore ships with **vanilla
defaults** (ACTION_MASK=0x2000 for Circle, ATTACK_MASK=0x8000 for Square)
and has two obvious `patch=1` lines at the top that remap users edit. The
README documents the 2-minute discovery procedure (open PCSX2 memory view
on `0x001DC470`, press a button, see which bit clears, set the mask).

## Implementation notes

### Hook site

Replace the `jr $ra` at `0x001ACDE4` with `j <trampoline>`. The function
epilogue has already restored `$ra` (from `$sp+0x38` at `0x001ACDD4`) and
the delay slot at `0x001ACDE8` pops the stack. Trampoline does:

```asm
  ; Check equipped-item == 1 (sword)
  lui   $at, 0x0107
  lbu   $t0, -0x3BBF($at)      ; t0 = *(0x0106C441)
  addiu $t1, $zero, 1
  bne   $t0, $t1, done         ; if not sword, skip
  nop

  ; Load processed pad halfword
  lui   $at, 0x001E
  lhu   $t0, -0x3B90($at)      ; t0 = *(0x001DC470) as u16

  ; Detect if ACTION and ATTACK bits differ
  andi  $t1, $t0, ACTION_MASK   ; nonzero if action bit is 1
  andi  $t2, $t0, ATTACK_MASK
  sltu  $t1, $zero, $t1         ; t1 = 1 iff action bit is 1
  sltu  $t2, $zero, $t2
  xor   $t3, $t1, $t2           ; t3 = 1 iff bits differ
  beq   $t3, $zero, done       ; same → no swap
  ori   $t4, $zero, (ACTION_MASK | ATTACK_MASK)  ; delay

  ; Swap: XOR both bits
  xor   $t0, $t0, $t4
  lui   $at, 0x001E
  sh    $t0, -0x3B90($at)      ; write back

done:
  jr    $ra
  nop
```

### Trampoline location

Place in an unused padding region; `0x0012EFCC` is used by the
velocity-cap pnach, `0x001A4984` is used by v18. We'll find a fresh
region via `tools/find_free_space.py` to avoid conflicts.

### Configurable masks

The pnach starts with:

```
// ==== USER CONFIG (edit if you've remapped in SotC's Button Config) ====
patch=1,EE,<TRAMP_ADDR+N>,word,<ACTION_MASK_imm_here>
patch=1,EE,<TRAMP_ADDR+M>,word,<ATTACK_MASK_imm_here>
```

with the `ori $t4, $zero, MASK` instruction encoded with the combined
mask as immediate — two small edits users can do by changing hex values.

Default: `ACTION_MASK = 0x2000`, `ATTACK_MASK = 0x8000` → combined
`0xA000`, encoded in the `ori $t4` as `0x3404A000`.

## Files

- `patch/0F0C4A9C_sword_button_swap_v1.pnach` — the patch (to be built)
- `docs/RESEARCH_SWORD_SWAP.md` — this document
- `tools/find_free_space.py` — (existing) find free code padding

## Credits

RE session spanning multiple iterations over about a month of wall-clock
time. Reversed via PINE IPC + PCSX2 debugger. All addresses verified
against PAL SCES-53326 CRC `0F0C4A9C`.
