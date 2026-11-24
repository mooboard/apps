-- the planetary Kp index now and tonight from NOAA's Space Weather Prediction Center, and the Kp your place needs to
-- see the aurora + a curtain over the hills grows with tonight's Kp, and turns red at the top in a big storm + your
-- place is the board's, and only NOAA's public feeds are asked
local POLE_LAT, POLE_LON = math.rad(80.7), math.rad(-72.7)   -- the geomagnetic north pole
local LEVELS = {"#34c759", "#34c759", "#34c759", "#34c759", "#ffd60a", "#ff9500", "#ff3b30", "#ff3b30", "#af52de"}
local STARS = {{4, 3}, {11, 7}, {19, 2}, {27, 5}, {35, 3}, {8, 12}, {31, 10}, {23, 13}, {38, 8}, {15, 9}}

local function fmt(v)
  local s = string.format("%.1f", v)
  if string.sub(s, -2) == ".0" then s = string.sub(s, 1, -3) end
  return s
end

local function hex(r, g, b, k)
  return string.format("#%02x%02x%02x", math.floor(math.min(255, r * k)), math.floor(math.min(255, g * k)),
    math.floor(math.min(255, b * k)))
end

local function maglat(lat, lon)
  local a, b = math.rad(lat), math.rad(lon)
  local s = math.sin(a) * math.sin(POLE_LAT) + math.cos(a) * math.cos(POLE_LAT) * math.cos(b - POLE_LON)
  return math.deg(math.asin(math.max(-1, math.min(1, s))))
end

local function kp_now()
  local rows = (data.kp or {}).value
  if type(rows) ~= "table" or #rows == 0 then return nil end
  for i = #rows, 1, -1 do
    local row = rows[i]
    local v = type(row) == "table" and tonumber(row.Kp or row.kp or row[2])
    if v then return v end
  end
  return nil
end

local function storm_watch()
  local scales = (data.scales or {}).value
  local g = 0
  if type(scales) == "table" then
    for _, day in ipairs({"0", "1"}) do
      local d = scales[day]
      local v = type(d) == "table" and type(d.G) == "table" and tonumber(d.G.Scale) or 0
      if v > g then g = v end
    end
  end
  return g > 0 and g + 4 or 0
end

local function scene(level, ms, k, south)
  local t = ms / 1000
  for i, s in ipairs(STARS) do
    local on = ((ms // 400 + i * 3) % 11) ~= 0
    if on then screen.pixel(s[1], s[2], hex(140, 150, 170, k)) end
  end
  -- the curtain: a bright green foot that waves above the hills, rays rising from it and fading, some brighter than
  -- others, and red on top in a storm
  local tall = 3 + level * 2
  for x = 2, 39 do
    local foot = 20 + math.floor(1.5 * math.sin(x * 0.25 + t * 0.7) + 0.5)
    local h = math.floor(tall * (0.45 + 0.55 * math.abs(math.sin(x * 0.45 + t * 0.6 + math.sin(x * 0.1) * 2))) + 0.5)
    local ray = 0.5 + 0.5 * math.sin(x * 1.3 + t * 2.2) ^ 2
    for j = 0, h - 1 do
      local y = foot - j
      if y < 2 then break end
      local up = j / math.max(1, h)
      if level >= 6 and j >= tall * 0.6 then
        screen.pixel(x, y, hex(200, 60, 140, k * ray * (1.1 - up * 0.5)))
      else
        screen.pixel(x, y, hex(60, 255, 140, k * (j == 0 and 1 or ray * (1 - up * 0.6))))
      end
    end
  end
  -- the hills and their pines
  for x = 1, 40 do
    local top = 26 + math.floor(1.5 * math.sin(x * 0.21) + 1 * math.sin(x * 0.53 + 1) + 0.5)
    screen.rect(x, top, 1, 31 - top, hex(16, 40, 30, k), true)
  end
  for _, px in ipairs({7, 18, 30}) do
    screen.line(px, 22, px - 2, 26, hex(10, 52, 34, k))
    screen.line(px, 22, px + 2, 26, hex(10, 52, 34, k))
    screen.line(px, 23, px, 27, hex(10, 52, 34, k))
  end
end

return {
  frame = function(ctx)
    local k = ctx.night and 0.6 or 1
    local now = kp_now()
    if not now then
      state.kp, state.tonight = nil, nil
      scene(1, ctx.monoMs, k * 0.7)
      screen.text("AURORA", 46, 20, 9, hex(161, 181, 189, k))
      screen.rect(46 + (ctx.monoMs // 60) % 60, 25, 6, 1, hex(60, 255, 140, k * 0.6), true)
      return
    end
    local tonight = math.max(now, storm_watch())
    state.kp, state.tonight = fmt(now), fmt(tonight)
    local need, m = nil, nil
    if ctx.lat and ctx.lon then
      m = maglat(ctx.lat, ctx.lon)
      need = math.max(0, math.ceil((63.5 - math.abs(m)) / 2))
      state.need = need > 9 and "9+" or tostring(need)
      state.look = (need <= 9 and tonight >= need) and (m >= 0 and "north" or "south") or "none"
    else
      state.need, state.look = nil, nil
    end
    scene(math.min(9, tonight), ctx.monoMs, k)
    local grey, white = hex(111, 135, 147, k), hex(255, 255, 255, k)
    screen.text("NOW", 46, 8, 6, grey)
    screen.text(state.kp, 46, 21, 13, white)
    screen.text("TONIGHT", 82, 8, 6, grey)
    screen.text(state.tonight, 82, 21, 13, white)
    if state.look and state.look ~= "none" then
      local on = (ctx.monoMs // 700) % 2 == 0
      screen.text(state.look == "north" and "LOOK NORTH" or "LOOK SOUTH", 46, 29, 6,
        on and hex(60, 255, 140, k) or hex(30, 150, 80, k))
      return
    end
    for i = 1, 9 do
      local lit = i <= math.floor(tonight + 0.5)
      local r, g, b = tonumber(LEVELS[i]:sub(2, 3), 16), tonumber(LEVELS[i]:sub(4, 5), 16), tonumber(LEVELS[i]:sub(6, 7), 16)
      screen.rect(46 + (i - 1) * 4, 27, 3, 2, hex(r, g, b, lit and k or k * 0.18), true)
    end
    if need then
      if need >= 1 and need <= 9 then screen.rect(46 + (need - 1) * 4, 25, 3, 1, white, true) end
      screen.text("NEED " .. state.need, 84, 29, 6, grey)
    end
  end
}
