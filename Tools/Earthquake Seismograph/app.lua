-- the world's latest earthquake from the USGS feed, its magnitude in a color for its level, how long ago, and how far
-- from the board + a seismograph pen draws a trace that shakes harder for a bigger quake + only the USGS public feed
-- is asked, and your place stays on the board
local LEVELS = {   -- up to this magnitude, its word and color
  {4, "minor", "#8aa0ad"}, {5, "light", "#34c759"}, {6, "moderate", "#ffd60a"},
  {7, "strong", "#ff9500"}, {8, "major", "#ff3b30"}, {99, "great", "#af52de"},
}
local MID = 18   -- the trace's middle row
local UNITS = {["Miles"] = {1, " mi"}, ["Kilometers"] = {1.609344, " km"}}

local function hex(r, g, b, k)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function dim(h, k)
  return hex(tonumber(h:sub(2, 3), 16), tonumber(h:sub(4, 5), 16), tonumber(h:sub(6, 7), 16), k)
end

local function commas(n)
  local s, tail = tostring(n), ""
  while #s > 3 do
    tail = "," .. string.sub(s, -3) .. tail
    s = string.sub(s, 1, -4)
  end
  return s .. tail
end

local function miles(lat1, lon1, lat2, lon2)
  local a, b, c, d = math.rad(lat1), math.rad(lon1), math.rad(lat2), math.rad(lon2)
  local h = math.sin((c - a) / 2) ^ 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ^ 2
  return 3958.8 * 2 * math.asin(math.min(1, math.sqrt(h)))
end

local function newest()
  local v = (data.quakes or {}).value
  if type(v) ~= "table" then return nil end
  local best = false
  for _, f in ipairs(v.features or {}) do
    local p = type(f) == "table" and f.properties
    if type(p) == "table" and tonumber(p.time) and tonumber(p.mag) and (not best or p.time > best.properties.time) then
      best = f
    end
  end
  return best
end

local function ago(sec)
  if sec < 60 then return "now" end
  if sec < 3600 then return (sec // 60) .. " min ago" end
  if sec < 86400 then return (sec // 3600) .. " h ago" end
  local d = sec // 86400
  return d .. (d == 1 and " day ago" or " days ago")
end

local function shake(tc, size)
  -- the pen's offset at time tc: a little noise, then every 8 s a quake's P wave and its bigger S wave dying out
  local p = tc % 8
  local amp = 0.5
  if p < 1 then amp = math.max(amp, size * 0.3)
  elseif p < 5 then amp = math.max(amp, size * math.exp(-(p - 1) * 0.8)) end
  return math.floor(amp * math.sin(tc * 37 + math.sin(tc * 11) * 2) + 0.5)
end

local function trace(ms, size, k, ink)
  screen.rect(1, 13, 126, 1, hex(22, 34, 42, k), true)
  screen.rect(1, 23, 126, 1, hex(22, 34, 42, k), true)
  local t, py = ms / 1000, nil
  for x = 1, 125 do
    local y = MID + shake(t - (125 - x) * 0.04, size)
    y = math.max(12, math.min(23, y))
    if py then screen.line(x - 1, py, x, y, ink) else screen.pixel(x, y, ink) end
    py = y
  end
  screen.rect(125, py, 2, 1, hex(255, 59, 48, k), true)
end

local function marquee(words, ms, k)
  local w = #words * 6
  if w <= 122 then
    screen.text(words, 2, 29, 6, hex(161, 181, 189, k))
  else
    -- 2 s still at the start, then it scrolls round once with a 60 dot gap
    local period = (w + 60) * 33 + 2000
    local off = math.max(0, ms % period - 2000) // 33
    screen.text(words, 2 - off, 29, 6, hex(161, 181, 189, k))
    screen.text(words, 2 - off + w + 60, 29, 6, hex(161, 181, 189, k))
    screen.rect(0, 0, 1, 32, "#000000", true)
    screen.rect(127, 0, 1, 32, "#000000", true)
  end
end

return {
  frame = function(ctx)
    local k = ctx.night and 0.55 or 1
    local q = newest()
    if q == nil then
      state.latest = nil
      trace(ctx.monoMs, 0, k, hex(111, 135, 147, k))
      screen.text("QUAKES", 2, 11, 9, hex(161, 181, 189, k))
      return
    end
    if not q then
      state.latest, state.mag, state.place, state.ago, state.away, state.level = "none", nil, nil, nil, nil, nil
      trace(ctx.monoMs, 0, k, hex(111, 135, 147, k))
      screen.text("ALL QUIET", 2, 11, 9, hex(161, 181, 189, k))
      return
    end
    local p = q.properties
    local mag = tonumber(p.mag)
    local place = tostring(p.place or "")
    for i = 1, #place - 4 do   -- "9 km NNW of La Tronosa, Panama" keeps the place after " of "
      if string.sub(place, i, i + 3) == " of " then
        place = string.sub(place, i + 4)
        break
      end
    end
    local level = LEVELS[#LEVELS]
    for _, l in ipairs(LEVELS) do
      if mag < l[1] then level = l break end
    end
    state.mag, state.place, state.level = string.format("%.1f", mag), place, level[2]
    state.latest = "M" .. state.mag .. " " .. place
    state.ago = ago(math.max(0, ctx.epochSec - p.time // 1000))
    local away = nil
    local where = q.geometry and q.geometry.coordinates
    if ctx.lat and ctx.lon and type(where) == "table" and tonumber(where[1]) and tonumber(where[2]) then
      local d = miles(ctx.lat, ctx.lon, where[2], where[1])
      local u = UNITS[settings.units] or UNITS["Miles"]
      away = commas(math.floor(d * u[1] / 10 + 0.5) * 10) .. u[2]
    end
    state.away = away
    local size = math.max(1, math.min(6, (mag - 2) * 1.4))
    trace(ctx.monoMs, size, k, hex(230, 237, 240, k))
    screen.text("M" .. state.mag, 2, 11, 9, dim(level[3], k))
    screen.text(string.upper(state.ago), 40, 8, 6, hex(111, 135, 147, k))
    marquee(string.upper(place) .. (away and ("   " .. string.upper(away)) or ""), ctx.monoMs, k)
  end
}
