# Seasonal faces

A board on the Seasonal clock face shows the event of the day: its picture, with the time on top. Between events it
shows the face it had before Seasonal was picked, or Classic. Boards check for new events once a day, and fetch an event the day before it starts.

## Add an event

1. Make a folder named after the event: `Seasonal/<Event Name>/`, for example `Seasonal/New Year/`.
2. Add the picture as `background.gif` or `background.png`.
   - 128 x 32 pixels.
   - Keep the outer ring of pixels black.
   - At most 100 frames, each at least 30 ms, and at most 256 KB.
   - Up to 256 colors across all frames. More are merged.
3. Add `face.json`:

   ```json
   {
     "id": "new-year",
     "name": "New Year",
     "start": "12-31",
     "end": "01-01",
     "clock": {"x": 64, "y": 9, "align": "center", "font": "clock", "size": 14, "color": "#ffd27a"}
   }
   ```

   | Key | What it is |
   | --- | --- |
   | `id` | Lowercase letters, digits and dashes. No app or other event may share it. |
   | `name` | The folder's name, exactly. |
   | `start`, `end` | `MM-DD` for every year, or `YYYY-MM-DD` for one year. Use the same form for both. An end before the start runs into the next year. Two events can't overlap. |
   | `clock.x` | The column the time lines up on, 0 to 127. |
   | `clock.y` | The top row of the digits, 0 to 31. |
   | `clock.align` | Which part of the time sits on `x`: `left`, `center` or `right`. |
   | `clock.font` | `clock`, `big` (Big Time's digits), `light` or `rounded`. |
   | `clock.size` | How tall the digits are, 6 to 28 rows. |
   | `clock.color` | The digits' color as `#rrggbb`. |
   | `version` | Optional, `X.Y.Z`. Raise it when you change the picture. |

   Every `clock` key is optional. Leave one out for its default: `64`, `9`, `center`, `clock`, `14` and `#ffffff`.
   The board keeps the time inside the black ring, whatever `x` and `y` say.

Festivals on the lunar calendar move every year, so give them a `YYYY-MM-DD` start and end, and add next year's dates
when you know them. Diwali 2026 is on November 8.

## Preview it

1. From this repo: `python3 tools/build.py`. It checks the rules and writes the packages and `index.json` to `dist/`.
2. From the firmware repo:

   ```sh
   ~/.local/bin/pio run -e sim
   PW_SIM_SEASONAL=~/.pixelwall-build/apps-store-repo/dist PW_SIM_SEASONAL_ID=new-year \
     ~/.pixelwall-build/pio/build/sim/program --scenario seasonal-preview --out ~/Desktop/seasonal-preview
   ```

   The frames are in `~/Desktop/seasonal-preview/seasonal-preview/`, at 10:42 on the event's first day.

## Publish it

1. Commit the folder and push this repo.
2. Run `~/.pixelwall-build/publish-apps-catalog.sh`. It builds, signs and uploads the catalog, and asks first.

Publish at least two days before the event starts. A board can take a day to check, and it fetches the event the day
before.
