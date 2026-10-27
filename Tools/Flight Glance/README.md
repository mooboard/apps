# Flight Glance

Live ADS-B aircraft on mooboard, with a detail card and a local radar view. Nearby mode uses the board's saved location and a 5/15/30/60/120 nautical-mile radius, selects the nearest five recent airborne aircraft, and rotates every 3/5/8 seconds.

Fill either Follow field with comma-separated callsigns or tail registrations to follow up to five aircraft worldwide instead of the local area. Use `-` for no followed targets. Common IATA flight numbers (UA, AA, DL, WN, AS, B6, NK, BA, LH, AF, KL, EK, QR, QF, AC, WS, F9, FR, U2) are normalized to ADS-B callsigns. Other airlines require their actual ICAO callsign. Examples: `UAL123,DAL456,N123AB`.

Details show callsign, registration, aircraft type, barometric altitude, ground speed, heading, and vertical rate. Aviation units use feet, knots, degrees, and feet/minute; Metric uses metres, kilometres/hour, degrees, and metres/second. Radar uses the board location and selected radius, with selected-target information beside the plot. Out-of-range followed targets remain in the detail rotation; local radar only plots targets within its radius.

The aircraft feed is polled every 15 seconds in nearby mode. Followed targets are polled in turn, one every 3 seconds. Positions older than 60 seconds and ground targets are excluded. Network errors and stale data are shown explicitly; no aircraft movement or flight data is fabricated. With a quiet sky the app shows a message and the actual board time. Missing location prompts setup. The app fetches only while rotating, locked, or open in its sheet, and only on a verified board.

Data: [adsb.lol](https://www.adsb.lol/), under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Nearby mode sends the saved board coordinates to this provider. Coverage depends on its receiver network. This is an original mooboard implementation inspired by the general flight-display concept; it uses no FlightWall branding, artwork, software, or proprietary data service.

Version 1.1.0 uses the dedicated `flightglance` renderer and requires firmware carrying it (the Flight Glance prototype build). Older firmware will report that a newer mooboard is needed. V1 provides radius tracking and followed aircraft with live reported metrics; polygon areas, route/ETA enrichment, and airline/type filters are not part of this version.
