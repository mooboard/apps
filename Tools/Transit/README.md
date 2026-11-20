# Transit

The next bus or train at your stop, from your city's free feed.

Near Boston it shows the stops near your board with no setup. Anywhere else, paste a feed link for your stop in your board's web app. It reads the MBTA predictions format and a plain list of arrivals. The first two arrivals show with a color for the route, and one that is a minute away flashes.

## Settings

- Feed link and stop name, for a stop of your own.
- Route, or all.
- Direction: both, outbound, or inbound.

## Cities

- Boston, from the MBTA, within about 37 miles of downtown.

For a stop of your own in Boston, use a link like https://api-v3.mbta.com/predictions?filter[stop]=place-sstat&sort=arrival_time&page[limit]=10&fields[prediction]=arrival_time,departure_time,direction_id
