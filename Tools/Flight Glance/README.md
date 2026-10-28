# Flight Glance

Live aircraft on the 128×32 mooboard panel. Version 1.2.0 has seven selectable views: Airline, Details, Route, Progress, Radar, Instruments, and Flight board. All screens tours these views for each aircraft while the app is held open. A normal app rotation can end before a full tour; select a view or hold the app open to watch the full tour.

## Aircraft and settings

Nearby mode uses the board's saved location and a 5/15/30/60/120 nautical-mile radius, selecting the nearest five recent airborne aircraft. Fill either Follow field with comma-separated callsigns or tail registrations to follow up to five aircraft worldwide instead. Use `-` for no followed targets. Common IATA flight numbers are normalized to ICAO callsigns (for example UA123 → UAL123); otherwise use the actual broadcast callsign. Followed aircraft can also show on the ground, without inventing an altitude.

Choose aviation or metric units, a 3/5/8-second page interval, callsign or tail title, and Clock / No flights / Dots / Blank when the sky is quiet. Offline, loading, missing-location and stale-data messages remain visible regardless of the quiet-sky preference. An amber corner indicates more than five nearby aircraft; the full tour also shows the total and a Too many flights page. Radar uses the board location and selected radius; worldwide targets outside that radius are labeled.

## Airlines

Every flight shows a plain plane with the airline's name as text. Unknown and private aircraft show a generic plane.

## Routes and estimates

[adsb.lol routeset](https://api.adsb.lol/docs) supplies probable routes from Virtual Radar Server standing data, not an airline schedule. Callsign, plausibility, coordinates and route geometry are checked before display. Multi-stop results select the segment that best fits the current position. Routes are marked EST, cached for up to 20 minutes, and negative lookups retry after a minute. A missing route says Route unavailable.

Progress is a geometric estimate: distance from origin divided by that distance plus remaining direct distance. It is not measured distance flown. Remaining distance and estimated travel time use the current position and ground speed. An arrival clock in the board's time zone, labeled ETA~, alternates with that travel time when the board clock is available. Estimates are withheld for low speed, ground/low-altitude aircraft, a heading away from the destination, and implausible durations. These estimates do not include approach, taxi, weather or schedule changes. A confirmed scheduled/live airline ETA is not available from this feed.

## Live data

Positions and reported metrics come from [adsb.lol](https://www.adsb.lol/), under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Nearby mode sends the board coordinates to that provider; route lookups send callsign and current aircraft coordinates. Coverage depends on its receiver network. Nearby data polls every 15 seconds; followed targets poll in turn, one every 3 seconds. Observations older than 60 seconds are excluded/marked stale. The app fetches while rotating, locked, or open in its sheet, on a verified board. No demo aircraft or synthetic movement appears in normal operation.

A firmware build carrying this version of `flightglance` is required (the expanded Flight Glance prototype). This is an original mooboard implementation and does not use FlightWall software or its proprietary service. It does not provide polygon areas, anchor-airport filters, per-airline/type/altitude filters, arbitrary unit combinations, or the FlightWall mobile app/Plus service. Brightness, sleep and timezone use the board's existing settings.
