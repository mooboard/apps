# Flight Glance

Live aircraft on the 128×32 mooboard panel. Version 1.3.0 has nine views and a tour that runs through Airline, Details, Route, Progress, Radar, Instruments, Flight board, Crew schedule, and Airport names. Hold the app open to watch the whole tour.

## Aircraft

Nearby mode shows the five closest aircraft around the board, or inside the areas you draw. Follow up to five callsigns or tail numbers anywhere with the two Follow fields. A flight number like UA123 becomes its callsign UAL123. A followed aircraft on the ground shows no made-up altitude.

## Airlines

Logos come from the [airlines-logos-dataset](https://github.com/imgmongelli/airlines-logos-dataset) by ICAO code, with pixel marks or a plain plane when there is none. The logo is the operating airline's, which can differ from a codeshare's ticket. Names come from [adsbdb](https://github.com/mrjackwills/adsbdb).

## Areas, filters, and units

Open Flight Glance on the board's page to draw areas on a map, set altitude limits, and filter by airline, aircraft class, speed, route, or anchor airport. Pick each unit, choose which fields show, and add two city clocks for a quiet sky.

## Crew schedules

Type legs as CSV, import a calendar file, use the board's Google Calendar, or link a private calendar. Each leg needs a flight number and two airports, like `UA123 ORD EWR`. Repeating flight events are turned away, so export each leg on its own. A Google refresh drops legs you deleted or moved.

## Routes and estimates

Routes come from [adsb.lol](https://api.adsb.lol/docs) standing data, are marked EST, and are asked again every 20 minutes. Progress and travel time are straight-line estimates. The arrival shows as ETA in the board's time, and a crew leg's arrival shows as SCH.

## Data

Positions come from [adsb.lol](https://www.adsb.lol/) under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), through mooboard's server when it answers and straight from adsb.lol when it doesn't. The app asks only while it is on screen, starting a few seconds before its turn. A refused or failed request rests a minute. Nearby mode sends the board's location to mooboard's server and adsb.lol, and a logo request sends only the airline code. Needs mooboard 0.4.0 or later.
