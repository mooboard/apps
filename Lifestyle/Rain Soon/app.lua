-- a heads-up when rain or snow starts within the hour, from Open-Meteo's 15 minute forecast at the board's place, no key
-- each slot's amount (mm) is the sum of the 15 minutes before its time, so a slot covers [time - 900, time)
local QUARTER, HOUR = 900, 3600
local LIGHT = 0.1          -- the least Open-Meteo reports
local STEADY = 0.5         -- 2 mm an hour
local HEAVY = 1.0          -- 4 mm an hour, a brighter bar

local DAY = {
  cloud = {161, 181, 189}, dimCloud = {58, 70, 80}, words = {255, 255, 255}, now = {159, 216, 255},
  quiet = {90, 110, 120}, drop = {60, 170, 255}, heavy = {159, 216, 255}, flake = {223, 232, 240},
  faint = {36, 80, 110}, dry = {29, 42, 51}, stale = {255, 149, 0},
}

local function paint(rgb, ctx)
  local k = ctx.night and 0.45 or 1
  return (math.floor(rgb[1] * k) << 16) | (math.floor(rgb[2] * k) << 8) | math.floor(rgb[3] * k)
end

local function least()
  if settings.warn == "Steady rain" then return STEADY end
  return LIGHT
end

-- the slot whose 15 minutes hold t: its amount and whether it snows, or nil when the forecast has no such slot
local function slotAt(m, t)
  local times, amounts, snow = m.time, m.precipitation, m.snowfall or {}
  for i = 1, #times do
    local ends = tonumber(times[i])
    if ends and ends - QUARTER <= t and t < ends then
      return tonumber(amounts[i]) or 0, (tonumber(snow[i]) or 0) > 0
    end
  end
  return nil
end

-- what the next hour holds: kind (rain, now, dry, or nil while waiting), seconds until it starts, and whether it snows
local function outlook(value, now)
  local m = type(value) == "table" and value.minutely_15
  if type(m) ~= "table" or type(m.time) ~= "table" or type(m.precipitation) ~= "table" then return nil end
  local need = least() - 0.000001
  local amount, snowing = slotAt(m, now)
  if amount == nil then return nil end   -- an old forecast says nothing about now
  if amount >= need then return "now", 0, snowing end
  local last = 0
  for i = 1, #m.time do
    local ends = tonumber(m.time[i]) or 0
    local starts = ends - QUARTER
    last = math.max(last, ends)
    if starts > now and starts <= now + HOUR and (tonumber(m.precipitation[i]) or 0) >= need then
      return "rain", starts - now, (tonumber((m.snowfall or {})[i]) or 0) > 0
    end
  end
  if last < now + HOUR then return nil end   -- the forecast stops short of the hour
  return "dry"
end

local function minutes(sec)
  return math.max(1, math.floor(sec / 60 + 0.5))
end

local function cloud(ctx, rgb)
  local c = paint(rgb, ctx)
  screen.circle(11, 10, 4, c)
  screen.circle(17, 8, 5, c)
  screen.circle(22, 11, 3, c)
  screen.rect(8, 11, 17, 4, c, true)
end

-- drops fall in five lanes under the cloud, each at its own height
local function drops(ctx, snow, rgb)
  local c = paint(rgb, ctx)
  for lane = 0, 4 do
    local x = 8 + lane * 4
    if snow then
      local y = 17 + ((ctx.monoMs // 150) + lane * 5) % 13
      screen.pixel(x + ((y + lane) // 3) % 2, y, c)
    else
      local y = 17 + ((ctx.monoMs // 60) + lane * 5) % 12
      screen.rect(x, y, 1, 2, c, true)
    end
  end
end

-- the next hour as four quarters, each lit by the rain in it
local function bar(ctx, m, now, need)
  for q = 0, 3 do
    local amount = slotAt(m, now + q * QUARTER + QUARTER // 2) or 0
    local rgb = DAY.dry
    if amount >= HEAVY then rgb = DAY.heavy
    elseif amount >= need then rgb = DAY.drop
    elseif amount >= LIGHT then rgb = DAY.faint end
    screen.rect(34 + q * 22, 22, 21, 2, paint(rgb, ctx), true)
  end
end

return {
  frame = function(ctx)
    local feed = data.rain or {}
    local now = tonumber(ctx.epochSec) or 0
    local kind, wait, snow
    if ctx.timeValid ~= false then kind, wait, snow = outlook(feed.value, now) end
    if kind == nil then
      state.next = "Waiting for the forecast"
      cloud(ctx, DAY.dimCloud)
      local dots = math.floor(ctx.monoMs / 400) % 4
      screen.text("RAIN SOON" .. string.sub("...", 1, dots), 34, 18, 9, paint(DAY.cloud, ctx))
    elseif kind == "dry" then
      state.next = "Dry this hour"
      cloud(ctx, DAY.dimCloud)
      screen.text("DRY THIS HOUR", 34, 18, 8, paint(DAY.quiet, ctx))
    else
      local what = snow and "SNOW" or "RAIN"
      local words
      if kind == "now" then
        words = snow and "SNOWING NOW" or "RAINING NOW"
        state.next = snow and "Snowing now" or "Raining now"
      else
        local n = minutes(wait)
        words = what .. " IN " .. n .. " MIN"
        state.next = (snow and "Snow" or "Rain") .. " in " .. n .. " min"
      end
      cloud(ctx, DAY.cloud)
      drops(ctx, snow, snow and DAY.flake or DAY.drop)
      screen.text(words, 34, 15, 8, paint(kind == "now" and DAY.now or DAY.words, ctx))
      bar(ctx, feed.value.minutely_15, now, least() - 0.000001)
    end
    if feed.status ~= nil and feed.status ~= "ok" and feed.value ~= nil then
      screen.pixel(126, 2, paint(DAY.stale, ctx))
    end
  end
}
