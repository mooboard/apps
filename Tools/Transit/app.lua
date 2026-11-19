-- reads two feed shapes
--   MBTA style: {"data": [{"attributes": {"arrival_time": "2026-11-19T14:32:00-05:00", "direction_id": 0},
--                          "relationships": {"route": {"data": {"id": "Red"}}}}]}
--   plain: {"arrivals": [{"route": "7", "at": 1795100000, "direction": 0}]} with at in epoch seconds or the same text
local CUM = {0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334}
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

local function arrivals(value)
  local out = {}
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
      local t = epoch(at.arrival_time) or epoch(at.departure_time)
      if t and (want == "all" or want == route) and (dir == nil or at.direction_id == dir) then
        out[#out + 1] = {route = route, at = t}
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
    local feed = data.stop or {}
    local value = feed.value
    local name = string.sub(tostring(settings.name), 1, 12)
    if string.sub(tostring(settings.feed), 1, 8) ~= "https://" then
      screen.text("SET A STOP", 24, 14, 9, "#a1b5bd")
      screen.text("IN THE APP", 24, 26, 9, "#6f8793")
      return
    end
    screen.text(name, 2, 7, 6, "#6f8793")
    if not value then
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
    if first then state.next = first.route .. " " .. ((first.at - now) // 60) .. " min" else
      screen.text("NONE SOON", 30, 24, 9, "#a1b5bd")
      state.next = "none"
    end
    if feed.status ~= "ok" and feed.status ~= nil then screen.pixel(126, 2, "#ff9500") end
  end
}
