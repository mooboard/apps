-- reads two feed shapes
--   MBTA style: {"data": [{"attributes": {"arrival_time": "2026-11-19T14:32:00-05:00", "direction_id": 0},
--                          "relationships": {"route": {"data": {"id": "Red"}}}}]}
--   plain: {"arrivals": [{"route": "7", "at": 1795100000, "direction": 0}]} with at in epoch seconds or the same text
local CUM = {0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334}
-- the cities with a free feed that finds the stops near the board, each one of the app's sources with the same near
local CITIES = {
  {name = "BOSTON", source = "boston", lat = 42.36, lon = -71.06, km = 60},
}
local COLORS = {
  Red = "#ff3b30", Orange = "#ff9500", Blue = "#3c8cff", Mattapan = "#ff3b30",
  ["Green-B"] = "#34c759", ["Green-C"] = "#34c759", ["Green-D"] = "#34c759", ["Green-E"] = "#34c759",
}

local function num(s, a, b) return tonumber(string.sub(s, a, b)) end

local function days(y, m, d)
  local leap = (y % 4 == 0 and (y % 100 ~= 0 or y % 400 == 0)) and 1 or 0
  local n = CUM[m] + d + ((m > 2) and leap or 0)
  local py = y - 1
  return py * 365 + py // 4 - py // 100 + py // 400 + n
end

-- epoch seconds from "2026-11-19T14:32:00-05:00" or a number, nil when it is neither
local function epoch(v)
  if type(v) == "number" then return v end
  if type(v) ~= "string" or #v < 19 then return nil end
  local y, mo, d, h, mi, s = num(v, 1, 4), num(v, 6, 7), num(v, 9, 10), num(v, 12, 13), num(v, 15, 16), num(v, 18, 19)
  if not (y and mo and d and h and mi and s) or mo < 1 or mo > 12 then return nil end
  local t = (days(y, mo, d) - days(1970, 1, 1)) * 86400 + h * 3600 + mi * 60 + s
  local sign = string.sub(v, 20, 20)
  if sign == "+" or sign == "-" then
    local off = (num(v, 21, 22) or 0) * 3600 + (num(v, 24, 25) or 0) * 60
    t = t - (sign == "-" and -off or off)
  end
  return t
end

local LABELS = {Red = "RED", Orange = "ORG", Blue = "BLU", Mattapan = "M", ["Green-B"] = "B", ["Green-C"] = "C", ["Green-D"] = "D", ["Green-E"] = "E"}

-- width of a size 9 line: digits 7, spaces 4, letters 11
local function wide(s)
  local w = 0
  for i = 1, #s do
    local b = string.byte(s, i)
    w = w + ((b >= 48 and b <= 57) and 7 or (b == 32 and 4 or 11))
  end
  return w
end

local function chipColor(route)
  if COLORS[route] then return COLORS[route] end
  if string.sub(route, 1, 3) == "CR-" then return "#af52de" end
  return "#ffd60a"
end

-- the closest city in CITIES within its km of the board's place, or nil
local function nearest(ctx)
  local lat, lon = tonumber(ctx.lat), tonumber(ctx.lon)
  if not (lat and lon) then return nil end
  local best, bestKm
  for i = 1, #CITIES do
    local c = CITIES[i]
    local r = math.pi / 180
    local a, b = math.sin((lat - c.lat) * r / 2), math.sin((lon - c.lon) * r / 2)
    local km = 2 * 6371 * math.asin(math.sqrt(math.min(1, a * a + math.cos(c.lat * r) * math.cos(lat * r) * b * b)))
    if km <= c.km and (bestKm == nil or km < bestKm) then best, bestKm = c, km end
  end
  return best
end

-- stop names from an MBTA feed's included stops, by id
local function stopNames(value)
  local names = {}
  local inc = value.included
  if type(inc) == "table" then
    for i = 1, #inc do
      local s = inc[i]
      if s.type == "stop" and s.attributes and s.attributes.name then names[s.id] = s.attributes.name end
    end
  end
  return names
end

local function arrivals(value)
  local out = {}
  local names = stopNames(value)
  local want = tostring(settings.route)
  local dir = settings.heading == "Outbound" and 0 or (settings.heading == "Inbound" and 1 or nil)
  local list = value.data
  local plain = value.arrivals
  if type(plain) == "table" then
    for i = 1, #plain do
      local a = plain[i]
      local t = epoch(a.at)
      if t and (want == "all" or want == tostring(a.route)) and (dir == nil or a.direction == nil or a.direction == dir) then
        out[#out + 1] = {route = tostring(a.route or "?"), at = t}
      end
    end
  elseif type(list) == "table" then
    for i = 1, #list do
      local p = list[i]
      local at = p.attributes or {}
      local rel = p.relationships and p.relationships.route and p.relationships.route.data
      local route = rel and rel.id or "?"
      local stop = p.relationships and p.relationships.stop and p.relationships.stop.data
      local t = epoch(at.arrival_time) or epoch(at.departure_time)
      if t and (want == "all" or want == route) and (dir == nil or at.direction_id == dir) then
        out[#out + 1] = {route = route, at = t, stop = stop and names[stop.id]}
      end
    end
  end
  table.sort(out, function(a, b) return a.at < b.at end)
  return out
end

local function row(y, a, now, ctx)
  local mins = (a.at - now) // 60
  if mins < 0 then mins = 0 end
  local route = LABELS[a.route] or string.sub(a.route, string.sub(a.route, 1, 3) == "CR-" and 4 or 1, 4)
  if string.sub(a.route, 1, 3) == "CR-" then route = "CR" end
  local c = chipColor(a.route)
  local w = 8 * #route + 3
  screen.rect(2, y - 8, w, 9, c, true)
  screen.text(route, 4, y, 8, "#000000")
  local label = mins == 0 and "NOW" or (mins .. " MIN")
  local color = mins <= 1 and ((ctx.monoMs // 400) % 2 == 0 and "#ffffff" or c) or "#ffffff"
  screen.text(label, 126 - wide(label), y, 9, color)
end

return {
  frame = function(ctx)
    -- your own stop's link first, else the stops near you in the closest city we have a feed for
    local own = string.sub(tostring(settings.feed), 1, 8) == "https://"
    local city = not own and nearest(ctx) or nil
    if not own and not city then
      screen.text("PICK YOUR STOP", 12, 14, 9, "#a1b5bd")
      screen.text("IN THE APP", 27, 26, 9, "#6f8793")
      state.next = "pick your stop"
      return
    end
    local feed = (own and data.stop or data[city.source]) or {}
    local value = feed.value
    if not value then
      screen.text(own and string.sub(tostring(settings.name), 1, 12) or "Near you", 2, 7, 6, "#6f8793")
      local dots = (ctx.monoMs // 400) % 4
      screen.text(string.sub("...", 1, dots), 2, 25, 11, "#a1b5bd")
      return
    end
    local list = arrivals(value)
    local now = ctx.epochSec
    local shown, first = 0, nil
    for i = 1, #list do
      if list[i].at >= now - 30 and shown < 2 then
        shown = shown + 1
        row(shown == 1 and 19 or 29, list[i], now, ctx)
        if not first then first = list[i] end
      end
    end
    -- your stop's name, or the name of the stop near you with the next one
    local name = own and string.sub(tostring(settings.name), 1, 12) or (first and first.stop) or "Near you"
    screen.text(string.sub(name, 1, 20), 2, 7, 6, "#6f8793")
    if first then state.next = first.route .. " " .. ((first.at - now) // 60) .. " min" else
      screen.text("NONE SOON", 30, 24, 9, "#a1b5bd")
      state.next = "none"
    end
    if feed.status ~= "ok" and feed.status ~= nil then screen.pixel(126, 2, "#ff9500") end
  end
}
