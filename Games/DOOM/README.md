# DOOM

The real DOOM engine and its shareware episode on the 128 by 32 panel.

With no game pad it plays the episode's recorded demos. With the game pad on your phone, Up and Down move, Left and Right turn, A fires, and B opens doors. Put the pad down and the demos start again. There is no sound, multiplayer, or saving.

The engine is in the firmware (renderer `doom`, 0.4.0-alpha.4 and later, S3 boards). This app carries only the game data, the DOOM v1.9 shareware `DOOM1.WAD`, compressed and cut into `data/wad-0.bin` to `wad-3.bin`. The package is about 1.75 MB, under the S3's 2 MB, and installing it needs about 1.81 MB free.

## Making the data

The WAD is id Software's, so this public repo never holds it or its chunks (`.gitignore`). Get `DOOM1.WAD` from id's `doom19s.zip`, then run

```sh
python3 builder/doom.py /path/to/DOOM1.WAD
```

It checks the file is the v1.9 shareware WAD (4,196,020 bytes, SHA-256 `1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771`) and writes the four chunks to `Games/DOOM/data/`. Any other file is refused. `builder/build.py` checks the chunks again. Without them, or with any that are wrong, it skips DOOM with a note and builds every other app. DOOM's row goes in `index2.json` alone, so boards that read only `index.json` never see it.

## License

DOOM and its data belong to id Software. The shareware data has its own terms, in the `README.TXT` inside `doom19s.zip`. The engine in the firmware is DoomGeneric under GPL-2.0-or-later. Both get a legal review before a public release.
