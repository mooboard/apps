# Games without a new firmware renderer

Firmware with the **game ABI 1 runtime** can run new games supplied as store
packages. The first runtime release is firmware **0.4.0-alpha.3**. It needs
one firmware update to add that runtime. Afterward, a game using ABI 1 needs only
a new signed store package and catalog row. Its app ID never enters the firmware
renderer list. Existing native games continue to work as before.

A game uses `"uses": "game"`. Its rules, automatic players, controls, sprites
and palette come from `data/game.json`, compiled by `builder/game.py` into
`data/game.bin` inside the package. No game has a C++ renderer or a
game-specific VM opcode.

## Make another game

1. Create `Games/My Game/` with `mooboard.json`, a 32×32 `icon.png`, a README,
   and `data/game.json`.
2. Use a new app ID, `"category": "Games"`, `"uses": "game"`, and
   `"minFirmware": "0.4.0-alpha.3"` in the usual format-2 manifest. An optional `speed`
   choice uses Slow, Normal and Fast, in that order.
3. Write the game source below as plain JSON assembly.
4. Run `python3 builder/build.py --out /private/tmp/my-games`. The builder
   compiles and validates the program before emitting any package. It also
   accepts already compiled `data/game.bin`; a game carries exactly one of those
   two files. The installed package always contains `data/game.bin` alone.
5. Publish through the existing signed catalog process. The firmware already
   knows how to execute ABI 1, so no firmware source edit or rebuild is needed
   for that game.

Source pushes alone do not publish packages. File upload/developer GIF apps are
unchanged; game programs install through the signed store. A game is listed in
index2.json alone (256 apps), never in the legacy index.json, and the installed
catalog-app limit (32) remains in force. Adding a
new runtime API, rather than a game using the existing API, can require a future
firmware update.

## Small complete program

This program increments a counter and draws it. Replace its `step` and `draw`
sections with a game's rules and graphics; the package format stays the same.

```json
{
  "abi": 1,
  "palette": ["#000000", "#75e8f0"],
  "memory": [0],
  "step": [
    ["load", 0, 0],
    ["const", 1, 1],
    ["add", 0, 0, 1],
    ["store", 0, 0],
    ["halt"]
  ],
  "draw": [
    ["const", 0, 0],
    ["clear", 0],
    ["const", 0, 4],
    ["const", 1, 10],
    ["load", 2, 0],
    ["const", 3, 1],
    ["digits", 0],
    ["halt"]
  ]
}
```

The source has only `abi`, `palette`, `sprites`, `memory`, `init`, `step`, `draw`
and `auto`. `step` and `draw` are required. `init` and `auto` are optional.

## Execution and input

- `init` runs once on entering the app. Memory begins with the source's
  `memory` words, with the rest zero. Leaving and reopening starts a new session.
- `step` runs at a fixed 20 ms. Frame delays catch up at most five ticks;
  rendering cadence does not change the rules' time step.
- `draw` runs at display cadence. It can read memory but cannot store memory or
  advance the random generator, so drawing twice does not advance gameplay.
- `auto`, when present, runs before `step` with no active controller. Its return
  register `r0` is the held-button mask. The runtime derives pressed edges.
- With an active controller, `auto` is skipped, including when it is idle.
  Short presses survive until the next tick. Directional controls follow the
  board's existing Gaming feature gate; automatic play also works without it.
- Each section starts with all 32 registers zero. Memory (512 signed 32-bit
  words) is the persistent state. Use `store` to keep a value between calls.

`input register, field` reads:

| Field | Value |
| --- | --- |
| 0 | Held buttons |
| 1 | Pressed buttons for this tick |
| 2 | Tick duration: 20 ms |
| 3 | 1 during automatic play, 0 with a controller |

Buttons are Up=1, Down=2, Left=4, Right=8, A=16, B=32; OR them to combine.
`setting register, index` reads a numeric app setting. Speed is setting 0,
with Slow=0, Normal=1, Fast=2. Game code decides how that choice affects play.

## Instructions

Register operands are integers 0–31. `a`, `b`, `c` below name registers; an
`immediate` is a signed 32-bit integer. `label` declares a section-local target.

| Instruction | Meaning |
| --- | --- |
| `halt` | Return; `r0` is the automatic player's result |
| `const a, immediate` / `mov a, b` | Load a constant / copy a register |
| `add/sub/mul/div/mod a, b, c` | Arithmetic using `b` and `c` |
| `and/or/xor/shl/shr a, b, c` | Bit operations; shifts use the low five bits of `c` |
| `eq/lt a, b, c` | Signed comparison, returning 0 or 1 |
| `label name` / `jump name` | Declare a target / jump to it |
| `jz/jnz a, name` | Jump if register `a` is zero / nonzero |
| `load/store a, word` | Read / write a constant memory word index |
| `loadi a, b` | Read `memory[r[b]]` into `r[a]` |
| `storei a, b` | Write `r[b]` into `memory[r[a]]` |
| `input a, field` / `setting a, index` | Read input / app setting |
| `random a, b` | Seeded random integer in `[0, r[b])`; zero when the bound is nonpositive |
| `overlap a` | AABB collision using eight consecutive registers |
| `cue look` / `cue look, color` | Flash the room's lights (see Game lights) |

Addition, subtraction, multiplication and shifts wrap at 32 bits. Right shift
is logical. Division truncates toward zero. Division by zero and signed
`INT32_MIN / -1` stop the program with a fault instead of invoking host undefined
behavior. Indexed memory is checked on each access.

Drawing instructions take the first register of a consecutive argument block:

| Instruction | Consecutive register arguments |
| --- | --- |
| `clear a` | palette index |
| `pixel a` | x, y, palette index |
| `rect a` | x, y, width, height, palette index |
| `line a` | x1, y1, x2, y2, palette index |
| `sprite a` | x, y, sprite index, flags (1 flip X, 2 flip Y) |
| `digits a` | x, y, nonnegative value (up to 999999), palette index |
| `overlap a` | x1, y1, w1, h1, x2, y2, w2, h2; result replaces register `a` |

Drawing is allowed only from `draw`. The palette has at most sixteen colors;
index 0 is black, and is transparent in sprites. Each of at most sixteen
sprites is eight rows of eight hexadecimal palette indices, e.g. `00111100`.
Coordinates refer to the whole 128×32 panel.
Drawing work and coordinates are bounded, even for a program with bad values.

## Game lights

Firmware **0.4.2-alpha.1** and later can flash the room's lights at a game's big
moments. Either way below needs `"minFirmware": "0.4.2-alpha.1"` or later, since
older boards refuse both. The builder refuses an app that asks for less.

The six looks, with the board's own timing and color:

| Look | Pulses | On ms | Off ms | Fade ms | Color |
| --- | --- | --- | --- | --- | --- |
| `hit` | 1 | 80 | 0 | 170 | `#ffffff` |
| `powerUp` | 1 | 150 | 0 | 350 | `#00ff6e` |
| `explosion` | 1 | 100 | 0 | 500 | `#ff5a00` |
| `levelClear` | 1 | 250 | 0 | 600 | `#ffc800` |
| `death` | 2 | 150 | 100 | 600 | `#ff0000` |
| `gameOver` | 3 | 200 | 150 | 1500 | `#ff0000` |

Use `death` when the player loses a life and `gameOver` when the run ends.

### A game program

`["cue", "death"]` flashes a look in its own color. `["cue", "powerUp", 8]`
flashes it in palette color 8 (1 to the last color; 0 is black). The op is
opcode 32 and its immediate holds the look's number (1 `hit` to 6 `gameOver`) in
the low four bits and the palette index plus one in the next five, zero for the
look's own color. A cue belongs in `step`, `init` or `auto`. The board stops a
program that cues from `draw`, so the builder refuses it. Cue once, when the
moment happens, and not on every step it lasts.

### A native game's manifest

A game with its own firmware renderer names its moments in `"lights"`, the last
key of `mooboard.json`. It maps each event to a look. Only `look` is required.
`color` is `#rrggbb`, `pulses` 1 to 3, `on` 40 to 600 ms, `off` 0 to 500 ms
(50 or more when there is more than one pulse) and `fade` 0 to 2000 ms. An event
left out stays dark.

```json
"lights": {
  "dead": {"look": "gameOver"},
  "chest": {"look": "powerUp", "color": "#ffc800"}
}
```

The builder writes the events in the renderer's order and each look's keys in
the board's order. Each renderer raises only these events:

| `uses` | Events |
| --- | --- |
| `pong` | `missed`, `scored` |
| `snake` | `crash`, `full`, `grow10` |
| `blocks` | `topOut`, `lines4`, `lines` |
| `maze` | `solved` |
| `breakout` | `ballLost`, `cleared` |
| `invaders` | `cannonHit`, `waveCleared`, `invaderHit` |
| `flappy` | `crash`, `pipes10` |
| `cycles` | `playerOut`, `roundWon`, `rivalOut` |
| `microracer` | `crash`, `milestone` |
| `pixelpinball` | `drain`, `targets`, `bumper` |
| `microrogue` | `hurt`, `dead`, `stairs`, `chest` |
| `spacelander` | `crash`, `landed` |
| `dinorunner` | `crash`, `score100` |
| `missiledefense` | `cityLost`, `lastCity`, `waveCleared`, `intercept` |
| `minesweeper` | `mine`, `cleared` |
| `wordguess` | `solved`, `outOfGuesses`, `miss` |
| `doom` | `died`, `hurt`, `powerUp`, `exit`, `blast` |

A game program (`"uses": "game"`) cues from its code and takes no `"lights"`.

## ABI and resource limits

ABI 1 has a 32-byte header (`MBG1`, little-endian version 1), a sixteen-color RGB
palette, at most 2048 fixed eight-byte instructions, up to sixteen 8×8 indexed
sprites, and at most 512 initial 32-bit words. The largest binary is 19,536
bytes. `game.py` is the reference encoder/validator; the firmware independently
validates the same format before installation and again when loading it.

Initialization allows at most 8192 instructions, each step 2048, automatic input
1024, and drawing 2048 plus a work allowance equivalent to four full panel
fills. Exceeding a budget stops that app for the current display turn. The
board's scheduler and other apps continue. Runtime faults show a red marker and
code: 1 missing program, 2 budget, 3 address, 4 division, 5 graphics outside draw,
6 state writes from draw, 7 invalid instruction.

The runtime exposes no filesystem, network, native pointers, arbitrary code
loading or persistent writes. Its scope is compact 2D games: integer logic,
state machines, sprites, drawing, collision tests, controls and automatic play.
Existing compiled games need not be converted. New game styles can use these
same primitives with their own packaged rules.
