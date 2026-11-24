# DOOM

The real DOOM engine and its shareware episode on the 128 by 32 panel.

With no game pad it plays the episode's recorded demos. With the game pad on your phone, Up and Down move, Left and Right turn, A fires, and B opens doors. Put the pad down and the demos start again. There is no sound, multiplayer, or saving.

The engine is in the firmware (renderer `doom`, 0.4.0-alpha.4 and later, S3 boards). This app carries the game data, the DOOM v1.9 shareware `DOOM1.WAD`, compressed and cut into `data/wad-0.bin` to `wad-3.bin`. From version 1.2 (firmware 0.4.5 and later) it also carries `data/tables.bin`, the engine's start-up tables, which the firmware no longer keeps in its own flash. The package is about 1.78 MB, under the S3's 2 MB, and installing it needs about 1.84 MB free.

## Making the data

The WAD is id Software's, so this public repo never holds it or its chunks (`.gitignore`). Get `DOOM1.WAD` from id's `doom19s.zip`, then run

```sh
python3 builder/doom.py /path/to/DOOM1.WAD
```

It checks the file is the v1.9 shareware WAD (4,196,020 bytes, SHA-256 `1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771`) and writes the four chunks to `Games/DOOM/data/`. Any other file is refused. `builder/build.py` checks the chunks again. Without them, or with any that are wrong, it skips DOOM with a note and builds every other app. DOOM's row goes in `index2.json` alone, so boards that read only `index.json` never see it.

`data/tables.bin` is in git. It comes from the engine's GPL source, not from id's data. When the engine's tables change, bake them in the firmware repo and write the file again with

```sh
PW_BAKE_DOOM_TABLES=/tmp/doom-tables.raw pio test -e native -f test_doom
python3 builder/doom.py --tables /tmp/doom-tables.raw
```

The script refuses tables whose SHA-256 is not the one the firmware checks.

## License

DOOM and its data belong to id Software. The shareware data has its own terms, in the `README.TXT` inside `doom19s.zip`. The engine in the firmware is DoomGeneric under GPL-2.0-or-later. Both get a legal review before a public release.
