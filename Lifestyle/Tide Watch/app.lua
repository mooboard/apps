-- tide watch + open-meteo sea level by place
local HOUR = 3600

-- size 6 advances, most capitals 7 and digits 6
local W6 = {E = 6, F = 6, L = 6, P = 6, S = 6, T = 6, Y = 6, Z = 6, I = 3, J = 4, M = 8, O = 8, Q = 8, W = 10,
            [" "] = 3, [":"] = 3, ["."] = 3, ["-"] = 5, ["/"] = 4, ["+"] = 6}
for d = 0, 9 do W6[tostring(d)] = 6 end

local function width6(s)
  local n = 0
  for i = 1, #s do n = n + (W6[string.sub(s, i, i)] or 7) end
  return n - 1
end

-- ink width of a size 13 time
local function width13(s)
  local n = 0
  for i = 1, #s do n = n + (string.sub(s, i, i) == ":" and 4 or 11) end
  return n - 1
end

local function days(y, m, d)
  if m <= 2 then y = y - 1 end
  local era = y // 400
  local yoe = y - era * 400
  local doy = (153 * ((m + 9) % 12) + 2) // 5 + d - 1
  return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468
end

-- seconds since 1970 of an api time in utc
local function epoch(s)
  if type(s) ~= "string" or #s < 16 then return nil end
  local y, mo, d = tonumber(string.sub(s, 1, 4)), tonumber(string.sub(s, 6, 7)), tonumber(string.sub(s, 9, 10))
  local h, mi = tonumber(string.sub(s, 12, 13)), tonumber(string.sub(s, 15, 16))
  if not (y and mo and d and h and mi) then return nil end
  return days(y, mo, d) * 86400 + h * 3600 + mi * 60
end

-- the board's utc offset from its own clock
local function offset(ctx)
  local d = ctx.hour * 3600 + ctx.minute * 60 + ctx.second - ctx.epochSec % 86400
  if d > 50400 then d = d - 86400 elseif d < -43200 then d = d + 86400 end
  return (d + 450) // 900 * 900
end

local function clock(t, ctx)
  local loc = (t + offset(ctx)) % 86400
  local h, m = loc // 3600, (loc % 3600) // 60
  local mm = m < 10 and ("0" .. m) or tostring(m)
  if ctx.clock24 then return h .. ":" .. mm, "" end
  local h12 = h % 12
  if h12 == 0 then h12 = 12 end
  return h12 .. ":" .. mm, h < 12 and "AM" or "PM"
end

local function span(sec)
  local m = (sec + 59) // 60
  if m < 60 then return m .. " MIN" end
  return (m // 60) .. "H " .. (m % 60) .. "M"
end

-- the series, its turns, and its kind
local tide = {kind = "wait"}

local function parse()
  local feed = data.tide
  local v = feed and feed.value
  local hourly = type(v) == "table" and v.hourly
  local times = type(hourly) == "table" and hourly.time
  local levels = type(hourly) == "table" and hourly.sea_level_height_msl
  if type(times) ~= "table" or type(levels) ~= "table" then return end
  local t0 = epoch(times[1])
  if not t0 then return end
  local vals, n, lo, hi, count = {}, #times, nil, nil, 0
  for i = 1, n do
    local x = levels[i]
    if type(x) == "number" then
      vals[i] = x
      count = count + 1
      if lo == nil or x < lo then lo = x end
      if hi == nil or x > hi then hi = x end
    else
      vals[i] = false
    end
  end
  if count < 12 or hi - lo < 0.08 then
    tide = {kind = "none"}
    return
  end
  local turns = {}
  for i = 2, n - 1 do
    local a, b, c = vals[i - 1], vals[i], vals[i + 1]
    if a and b and c then
      local high, low = b > a and b >= c, b < a and b <= c
      if high or low then
        local den = a - 2 * b + c
        local off = den ~= 0 and 0.5 * (a - c) / den or 0
        if off > 0.5 then off = 0.5 elseif off < -0.5 then off = -0.5 end
        turns[#turns + 1] = {t = t0 + (i - 1) * HOUR + math.floor(off * HOUR + 0.5), high = high,
                             h = b - 0.25 * (a - c) * off}
      end
    end
  end
  tide = {kind = "ok", t0 = t0, vals = vals, n = n, turns = turns}
end

-- the level at a time, nil outside the series
local function level(t)
  local x = (t - tide.t0) / HOUR
  local i = math.floor(x)
  if i < 0 or i + 1 >= tide.n then return nil end
  local a, b = tide.vals[i + 1], tide.vals[i + 2]
  if not (a and b) then return a or b or nil end
  local f = (1 - math.cos((x - i) * math.pi)) / 2
  return a + (b - a) * f
end

local function range(now)
  local lo, hi, seen = 0, 0, false
  for k = -12, 12 do
    local v = level(now + k * HOUR)
    if v then
      if not seen or v < lo then lo = v end
      if not seen or v > hi then hi = v end
      seen = true
    end
  end
  if hi - lo < 0.05 then hi = lo + 0.05 end
  return lo, hi
end

local function nextTurn(now)
  for i = 1, #tide.turns do
    local turn = tide.turns[i]
    if turn.t > now - 900 then return turn end
  end
  return nil
end

local function waitText(ctx, title, words)
  screen.text(title, 64 - width6(title) // 2, 14, 6, "#6f8793")
  if words then
    screen.text(words, 64 - width6(words) // 2, 25, 6, "#a1b5bd")
  else
    local dots = string.sub("...", 1, (ctx.monoMs // 400) % 4)
    screen.text("TIDE WATCH" .. dots, 64 - width6("TIDE WATCH") // 2, 25, 6, "#a1b5bd")
  end
end

-- a staff gauge in the water
local function gauge(ctx, frac, rising)
  local wl = 27 - math.floor(frac * 21 + 0.5)
  for y = 3, 29 do
    local c = y > wl and "#3b2a1a" or "#8a5a30"
    screen.rect(17, y, 3, 1, c, true)
    if y % 4 == 0 then screen.pixel(18, y, y > wl and "#6b5236" or "#e0c090") end
  end
  local ph = ctx.monoMs / 420
  for x = 3, 33 do
    if x < 17 or x > 19 then
      local s = math.sin(x * 0.55 + ph)
      local y = wl + (s > 0.35 and 0 or 1)
      screen.rect(x, y + 1, 1, 29 - y, "#0a2c48", true)
      screen.pixel(x, y, s > 0.8 and "#bfe6ff" or "#3caaff")
    end
  end
  local bob = (ctx.monoMs // 180) % 4
  local ay = rising and (wl - 6 - bob) or (wl - 9 + bob)
  if ay < 3 then ay = 3 end
  for k = 0, 2 do
    local y = rising and (ay + k) or (ay + 2 - k)
    screen.pixel(28 - k, y, "#ffffff")
    screen.pixel(28 + k, y, "#ffffff")
  end
end

local function nowPage(ctx, now, turn)
  local lo, hi = range(now)
  local cur = level(now) or lo
  local frac = (hi and hi > lo) and (cur - lo) / (hi - lo) or 0.5
  gauge(ctx, frac, turn.high)
  local title = turn.high and "HIGH TIDE" or "LOW TIDE"
  screen.text(title, 40, 8, 6, turn.high and "#9fd8ff" or "#a1b5bd")
  local time, half = clock(turn.t, ctx)
  screen.text(time, 40, 23, 13, "#ffffff")
  if half ~= "" then screen.text(half, 42 + width13(time), 23, 8, "#6f8793") end
  local rest = turn.t - now
  screen.text(rest <= 900 and "NOW" or ("IN " .. span(rest)), 40, 30, 6, rest <= 900 and "#ffb81c" or "#6f8793")
end

-- four hours back and twenty ahead
local function curvePage(ctx, now)
  local lo, hi = range(now)
  local start, step = now - 4 * HOUR, 24 * HOUR / 123
  local nowX = 2 + math.floor(4 * HOUR / step + 0.5)
  for x = 2, 125 do
    local v = level(start + (x - 2) * step)
    if v then
      local y = 22 - math.floor((v - lo) / (hi - lo) * 12 + 0.5)
      if y < 23 then screen.rect(x, y + 1, 1, 23 - y, "#0b2a40", true) end
      screen.pixel(x, y, x < nowX and "#1f5a80" or "#3caaff")
    end
  end
  for i = 1, #tide.turns do
    local turn = tide.turns[i]
    if turn.t >= start and turn.t <= start + 24 * HOUR then
      local x = 2 + math.floor((turn.t - start) / step + 0.5)
      local time, half = clock(turn.t, ctx)
      local words = time .. (half == "" and "" or (" " .. half))
      local w = width6(words)
      local lx = x - w // 2
      if lx < 2 then lx = 2 elseif lx + w > 125 then lx = 125 - w end
      screen.text(words, lx, turn.high and 8 or 30, 6, turn.high and "#9fd8ff" or "#6f8793")
    end
  end
  local v = level(now)
  if v then
    local y = 22 - math.floor((v - lo) / (hi - lo) * 12 + 0.5)
    local on = (ctx.monoMs // 500) % 2 == 0
    screen.rect(nowX - 1, y - 1, 3, 3, on and "#ffffff" or "#9fd8ff", true)
  end
end

return {
  data = function()
    parse()
  end,
  frame = function(ctx)
    if tide.kind == "wait" then parse() end
    local feed = data.tide
    if tide.kind == "none" then
      state.next = "No tide here"
      waitText(ctx, "TIDE WATCH", "NO SEA NEARBY")
      return
    end
    if tide.kind ~= "ok" then
      local down = feed and (feed.status == "error" or feed.status == "offline")
      state.next = down and "Offline" or "Waiting for data"
      waitText(ctx, "TIDE WATCH", down and "TIDES OFFLINE" or nil)
      return
    end
    local now = ctx.epochSec
    local turn = nextTurn(now)
    if not turn or not level(now) then
      state.next = "Offline"
      waitText(ctx, "TIDE WATCH", "TIDES OFFLINE")
      return
    end
    local time, half = clock(turn.t, ctx)
    state.next = (turn.high and "High at " or "Low at ") .. time .. (half == "" and "" or (" " .. half))
    local curve = settings.curve and (ctx.monoMs // 8000) % 2 == 1
    if curve then curvePage(ctx, now) else nowPage(ctx, now, turn) end
    if feed and feed.status ~= "ok" and feed.status ~= nil and feed.status ~= "loading" then
      screen.pixel(125, 2, "#ff9500")
    end
  end
}
