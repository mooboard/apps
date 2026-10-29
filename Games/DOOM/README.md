# DOOM

An actual DoomGeneric engine port with the unmodified DOOM v1.9 shareware IWAD. Engine code runs in firmware; the store app supplies game data. It uses the board's existing display, PSRAM and flash. No added hardware.

The automatic player shows DOOM's original recorded gameplay demo. On a board with game-pad support, Up/Down moves, Left/Right turns, A fires and B opens doors. Returning to automatic play starts the recorded demo again. The small display is silent and does not include network multiplayer or saved games.

Prepare the game data, then build the versioned catalog:

```sh
python3 builder/kit/doom.py
python3 builder/build.py --catalog-v2 --out dist-v2
```

The preparation script downloads only the first, shareware episode and verifies its SHA-256 fingerprint. It can also take `--wad /path/to/doom1.wad`. The WAD is compressed into four files, each within the store's 512 KB entry limit. Prepared data is ignored by Git; source pushes do not redistribute it.

This app needs firmware 0.4.1 with the native DOOM engine. Publish the signed extended catalog under the **catalog-v2** release tag. The default builder keeps this app out of the legacy 64-app catalog, so old boards retain their existing store endpoint. Source pushes alone do not publish a catalog or install firmware.

DOOM and its game data belong to id Software. DoomGeneric engine source is GPL-2.0-or-later and is included with the firmware's complete corresponding source. Game data has its own shareware terms and is not covered by the engine's GPL. Review the original shareware distribution's terms when distributing data packages. Data reference: <https://github.com/Doom-Utils/shareware-collection/tree/master/Doom%201.9>.
