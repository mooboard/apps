local RAD = math.pi / 180
local INCL = 51.64 * RAD
local PERIOD = 5575          -- seconds around
local SPIN = 360 / 86164     -- degrees the ground turns each second
local REACH = 12.5           -- degrees from you where the station is 10 degrees up
local MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}
local CUM = {0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334}
-- peak month, day, name, hourly rate
local SHOWERS = {
  {1, 3, "QUADRANTIDS"}, {4, 22, "LYRIDS"}, {5, 6, "ETA AQUARIIDS"}, {8, 12, "PERSEIDS"},
  {10, 21, "ORIONIDS"}, {11, 17, "LEONIDS"}, {12, 14, "GEMINIDS"}, {12, 22, "URSIDS"},
}
-- year, month, day, kind, and where it is seen: a lunar one's hour of greatest eclipse (UT), seen wherever the moon is
-- up within an hour of it, and a solar one's regions, from NASA's eclipse lists
local ECLIPSES = {
  {2027, 2, 6, "RING SOLAR", {"SA", "AN", "WSAF"}}, {2027, 8, 2, "TOTAL SOLAR", {"AF", "EU", "ME", "WSAS"}},
  {2028, 1, 12, "PART LUNAR", 4.22}, {2028, 1, 26, "RING SOLAR", {"ENA", "CA", "SA", "WEU", "NWAF"}},
  {2028, 7, 6, "PART LUNAR", 18.33}, {2028, 7, 22, "TOTAL SOLAR", {"SEAS", "AU", "NZ"}},
  {2028, 12, 31, "TOTAL LUNAR", 16.87}, {2029, 1, 14, "PART SOLAR", {"NA", "CA"}},
  {2029, 6, 12, "PART SOLAR", {"ARCTIC", "SCAN", "ALASKA", "NAS", "NCAN"}}, {2029, 6, 26, "TOTAL LUNAR", 3.37},
  {2029, 7, 11, "PART SOLAR", {"SSA"}}, {2029, 12, 5, "PART SOLAR", {"SSA", "AN"}},
  {2029, 12, 20, "TOTAL LUNAR", 22.7}, {2030, 6, 1, "RING SOLAR", {"EU", "NAF", "ME", "AS", "ARCTIC", "ALASKA"}},
  {2030, 6, 15, "PART LUNAR", 18.55}, {2030, 11, 25, "TOTAL SOLAR", {"SAF", "SEAS", "AU", "AN"}},
}
-- each region as boxes of south, north, west, and east edges in degrees
local REGIONS = {
  NA = {{15, 72, -170, -52}}, ENA = {{15, 72, -100, -52}}, CA = {{5, 25, -120, -58}}, SA = {{-56, 13, -82, -34}},
  SSA = {{-56, -30, -76, -52}}, EU = {{35, 72, -25, 45}}, WEU = {{35, 72, -25, 15}}, AF = {{-35, 37, -18, 52}},
  NAF = {{15, 37, -18, 35}}, NWAF = {{5, 37, -18, 15}}, WSAF = {{-35, 37, -18, 15}, {-35, -10, 15, 52}},
  SAF = {{-35, -15, 10, 52}}, ME = {{12, 42, 34, 63}}, AS = {{0, 78, 45, 180}}, WSAS = {{0, 78, 45, 95}, {0, 30, 95, 125}},
  NAS = {{50, 78, 45, 180}}, SEAS = {{-11, 28, 92, 141}}, AU = {{-45, -10, 112, 155}}, NZ = {{-48, -34, 165, 179}},
  AN = {{-90, -60, -180, 180}}, ARCTIC = {{66, 90, -180, 180}}, ALASKA = {{51, 72, -170, -130}},
  NCAN = {{55, 84, -141, -52}}, SCAN = {{55, 72, 4, 32}},
}
local J2000 = 946728000      -- 2000 Jan 1 12:00 UT
local PHASES = {"NEW MOON", "WAXING CRESCENT", "FIRST QUARTER", "WAXING GIBBOUS", "FULL MOON", "WANING GIBBOUS",
                "LAST QUARTER", "WANING CRESCENT"}

local function dayno(y, m, d)
  local leap = (y % 4 == 0 and (y % 100 ~= 0 or y % 400 == 0)) and 1 or 0
  local n = CUM[m] + d
  if m > 2 then n = n + leap end
  local py = y - 1
  return py * 365 + py // 4 - py // 100 + py // 400 + n
end

local function wrap(deg)
  deg = deg % 360
  if deg > 180 then deg = deg - 360 end
  return deg
end

-- degrees between two places on the ground
local function between(la1, lo1, la2, lo2)
  local a, b = la1 * RAD, la2 * RAD
  local c = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos((lo2 - lo1) * RAD)
  if c > 1 then c = 1 elseif c < -1 then c = -1 end
  return math.acos(c) / RAD
end

-- seconds until the station is next within reach of the place, 0 when it is now, nil when none within 12 hours
local function next_pass(lat0, lon0, up, mylat, mylon)
  local s = math.sin(lat0 * RAD) / math.sin(INCL)
  if s > 1 then s = 1 elseif s < -1 then s = -1 end
  local u0 = math.asin(s)
  if not up then u0 = math.pi - u0 end
  local node = lon0 - math.atan(math.cos(INCL) * math.sin(u0), math.cos(u0)) / RAD
  local rate = 2 * math.pi / PERIOD
  for t = 0, 43200, 120 do
    local u = u0 + rate * t
    local la = math.asin(math.sin(INCL) * math.sin(u)) / RAD
    local lo = node - SPIN * t + math.atan(math.cos(INCL) * math.sin(u), math.cos(u)) / RAD
    if between(la, lo, mylat, mylon) <= REACH then return t end
  end
  return nil
end

local function long(sec)
  local m = math.floor(sec / 60 + 0.5)
  if m < 60 then return m .. " MIN" end
  return (m // 60) .. "H " .. (m % 60) .. "M"
end

local function when(m, d) return MONTHS[m] .. " " .. d end

local function nextShower(y, m, d)
  local today = dayno(y, m, d)
  local best, bestDays, active
  for i = 1, #SHOWERS do
    local s = SHOWERS[i]
    local days = dayno(y, s[1], s[2]) - today
    if days < -4 then days = dayno(y + 1, s[1], s[2]) - today end
    if best == nil or days < bestDays then best, bestDays = s, days end
  end
  return best, bestDays
end

-- the sun's declination and the longitude it is overhead, n days from 2000 Jan 1 12:00 UT
local function sunAt(n)
  local L = (280.460 + 0.9856474 * n) % 360
  local g = (357.528 + 0.9856003 * n) * RAD
  local lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * RAD
  local eps = (23.439 - 0.0000004 * n) * RAD
  local dec = math.asin(math.sin(eps) * math.sin(lam)) / RAD
  local ra = math.atan(math.cos(eps) * math.sin(lam), math.cos(lam)) / RAD
  return dec, wrap(ra - (280.46061837 + 360.98564736629 * n))
end

-- a lunar eclipse is seen where the moon, opposite the sun, is up within an hour of its greatest
local function moonUp(y, m, d, ut, lat, lon)
  local day = dayno(y, m, d) - dayno(2000, 1, 1)
  for dt = -1, 1 do
    local dec, slon = sunAt(day + (ut + dt - 12) / 24)
    if between(lat, lon, -dec, wrap(slon + 180)) < 90 then return true end
  end
  return false
end

local function seen(e, lat, lon)
  if lat == nil or lon == nil then return true end
  local where = e[5]
  if type(where) == "number" then return moonUp(e[1], e[2], e[3], where, lat, lon) end
  for i = 1, #where do
    local boxes = REGIONS[where[i]] or {}
    for j = 1, #boxes do
      local b = boxes[j]
      if lat >= b[1] and lat <= b[2] and lon >= b[3] and lon <= b[4] then return true end
    end
  end
  return false
end

local cachedKey, cachedEclipse, cachedDays
local function nextEclipse(y, m, d, lat, lon)
  local key = y * 10000 + m * 100 + d .. "|" .. tostring(lat) .. "|" .. tostring(lon)
  if key == cachedKey then return cachedEclipse, cachedDays end
  local today = dayno(y, m, d)
  cachedKey, cachedEclipse, cachedDays = key, nil, nil
  for i = 1, #ECLIPSES do
    local e = ECLIPSES[i]
    local days = dayno(e[1], e[2], e[3]) - today
    if days >= 0 and seen(e, lat, lon) then
      cachedEclipse, cachedDays = e, days
      break
    end
  end
  return cachedEclipse, cachedDays
end

-- the moon's phase at t (Meeus' low-precision phase angle): its name, the part lit, and whether it is waxing
local function moonAt(t)
  local n = (t - J2000) / 86400
  local D = (297.8501921 + 12.19074912 * n) % 360
  local M = (357.5291092 + 0.98560028 * n) % 360
  local Mp = (134.9633964 + 13.06499295 * n) % 360
  local function s(deg) return math.sin(deg * RAD) end
  local i = 180 - D - 6.289 * s(Mp) + 2.100 * s(M) - 1.274 * s(2 * D - Mp) - 0.658 * s(2 * D) - 0.214 * s(2 * Mp)
            - 0.110 * s(D)
  local e = (180 - i) % 360
  return PHASES[math.floor((e + 22.5) / 45) % 8 + 1], (1 + math.cos(i * RAD)) / 2, e < 180
end

-- tonight is 10 pm, or now from 10 pm to 6 am
local function tonight(ctx)
  local t = tonumber(ctx.epochSec) or 0
  local h = tonumber(ctx.hour) or 22
  if h >= 6 and h < 22 then t = t + (22 - h) * 3600 - (tonumber(ctx.minute) or 0) * 60 end
  return t
end

local function stars(ctx, n)
  for i = 1, n do
    local x = (i * 37) % 126 + 1
    local y = (i * 17) % 30 + 1
    if (ctx.monoMs // 300 + i) % 5 ~= 0 then screen.pixel(x, y, "#3a4650") end
  end
end

-- earth's edge and the station's orbit share one center, so the station curves with the earth
local EX, EY, EARTH, ORBIT = 20, 70, 48, 58
local SWING = math.asin(17 / ORBIT)

local function drawIss(ctx, st)
  stars(ctx, 14)
  for x = 2, 38 do
    local dx = x - EX
    local top = math.floor(EY - math.sqrt(EARTH * EARTH - dx * dx) + 0.5)
    screen.rect(x, top + 1, 1, 31 - top, "#0e3a52", true)
    screen.pixel(x, top, "#1f7aa8")
  end
  local a = (ctx.monoMs % 6000) / 6000
  local t = (a * 2 - 1) * SWING
  local sx = math.floor(EX + ORBIT * math.sin(t) + 0.5)
  local sy = math.floor(EY - ORBIT * math.cos(t) + 0.5)
  screen.rect(sx - 1, sy, 3, 1, "#c8ced8", true)
  screen.rect(sx - 3, sy - 1, 2, 3, "#3caaff", true)
  screen.rect(sx + 2, sy - 1, 2, 3, "#3caaff", true)
  screen.text("ISS", 46, 9, 6, "#6f8793")
  local text, color = st.text, st.color
  screen.text(text, 46, 25, st.size, color)
end

local function drawShower(ctx, name, days, m, d)
  stars(ctx, 10)
  for i = 0, 2 do
    local phase = ((ctx.monoMs // 40) + i * 17) % 50
    local x = 2 + phase - i * 4
    local y = 2 + (phase * 12) // 50 + i * 7
    for k = 0, 5 do
      screen.pixel(x - k, y - k // 2, k == 0 and "#ffffff" or (k < 3 and "#9fd8ff" or "#3a5a70"))
    end
  end
  screen.text(name, 46, 9, 6, "#6f8793")
  local line = days <= 0 and (days == 0 and "PEAK TODAY" or "NOW") or (days == 1 and "TOMORROW" or (days .. " DAYS"))
  screen.text(line, 46, 21, 9, days <= 1 and "#ffffff" or "#ffb81c")
  screen.text(when(m, d), 46, 30, 6, "#6f8793")
end

local function drawEclipse(ctx, e, days)
  local solar = string.sub(e[4], -5) == "SOLAR"
  local ox = 11 + math.floor(math.sin(ctx.monoMs / 1500) * 4)
  if solar then
    screen.circle(16, 16, 11, "#ffb81c")
    screen.circle(16 + (ox - 11), 16, 10, "#050508")
  else
    screen.circle(16, 16, 11, "#c8ced8")
    screen.circle(16 + (ox - 11) + 4, 16, 10, "#7a1e1e")
  end
  screen.text(e[4], 36, 9, 6, "#6f8793")
  screen.text(when(e[2], e[3]), 36, 22, 9, "#ffffff")
  screen.text(tostring(e[1]) .. "  " .. (days == 0 and "TODAY" or (days .. " DAYS")), 36, 31, 6, "#ffb81c")
end

local function drawMoon(ctx, name, lit, waxing)
  -- lit from the right while waxing in the north, from the left in the south
  local right = waxing ~= ((tonumber(ctx.lat) or 0) < 0)
  for dy = -11, 11 do
    local w = math.sqrt(121 - dy * dy)
    local half = math.floor(w + 0.5)
    screen.rect(16 - half, 16 + dy, 2 * half + 1, 1, "#1a1c22", true)
    if lit >= 0.02 and w >= 1 then
      local t = w * (1 - 2 * lit)
      local x0, x1 = math.floor(16 + t + 0.5), 16 + half
      if not right then x0, x1 = 16 - half, math.floor(16 - t + 0.5) end
      if x1 >= x0 then screen.rect(x0, 16 + dy, x1 - x0 + 1, 1, "#e8e4d0", true) end
    end
  end
  local cut = #name
  for i = 1, #name do
    if string.sub(name, i, i) == " " then cut = i break end
  end
  screen.text("TONIGHT", 36, 9, 6, "#6f8793")
  local pct = tostring(math.floor(lit * 100 + 0.5))
  screen.text(pct .. "% LIT", 126 - (6 * #pct + 27), 9, 6, "#ffb81c")   -- right at 125, 6 a digit at size 6
  screen.text(string.sub(name, 1, cut - 1), 36, 19, 8, "#ffffff")
  screen.text(string.sub(name, cut + 1), 36, 28, 8, "#ffffff")
end

local function pages()
  local list = {}
  if settings.iss then list[#list + 1] = "iss" end
  if settings.showers then list[#list + 1] = "showers" end
  if settings.eclipses then list[#list + 1] = "eclipses" end
  if settings.moon ~= false then list[#list + 1] = "moon" end
  return list
end

local station = {text = "LOCATING", color = "#a1b5bd", size = 9}

return {
  data = function()
    local feed = data.iss
    local v = feed and feed.value
    if not v or v.latitude == nil then return end
    local lat, lon, ts = tonumber(v.latitude), tonumber(v.longitude), tonumber(v.timestamp)
    -- the board's place, from the last frame
    local mylat, mylon = tonumber(ctx.lat), tonumber(ctx.lon)
    if not (lat and lon and ts) then return end
    local last = state.pl
    local up = state.up
    if last and ts > state.pt then
      if math.abs(lat - last) > 0.01 then up = lat > last end
    end
    state.pl, state.pt, state.up = lat, ts, up
    state.at = ts
    if up == nil then return end
    if not (mylat and mylon) then state.next = "waiting for the board's place" return end
    local t = next_pass(lat, lon, up, mylat, mylon)
    state.t0, state.pass = ts, t
    if t == nil then state.next = "none in 12 hours" else state.next = t == 0 and "overhead" or long(t) end
  end,
  frame = function(ctx)
    local sh, shDays = nextShower(ctx.year, ctx.month, ctx.day)
    state.shower = sh[3] .. " " .. shDays
    local ec, ecDays = nextEclipse(ctx.year, ctx.month, ctx.day, tonumber(ctx.lat), tonumber(ctx.lon))
    state.eclipse = ec and (ec[4] .. " " .. ecDays) or "none"
    local phase, lit, waxing = moonAt(tonight(ctx))
    state.moon = phase .. " " .. math.floor(lit * 100 + 0.5)
    local list = pages()
    if #list == 0 then screen.text("SPACE", 44, 20, 9, "#6f8793") return end
    local page = list[(ctx.monoMs // 6000) % #list + 1]
    if page == "iss" then
      local st = station
      if state.pass ~= nil and state.t0 then
        local rest = state.pass - (ctx.epochSec - state.t0)
        if state.pass == 0 or rest <= 0 then
          st.text, st.color, st.size = "OVERHEAD", (ctx.monoMs // 400) % 2 == 0 and "#ffffff" or "#3caaff", 9
        else
          st.text, st.color, st.size = long(rest), "#3caaff", 11
        end
      elseif state.at and state.up ~= nil and ctx.lat and state.next ~= "waiting for the board's place" then
        st.text, st.color, st.size = "NONE SOON", "#a1b5bd", 9
      else
        st.text, st.color, st.size = "LOCATING", "#a1b5bd", 9
      end
      drawIss(ctx, st)
    elseif page == "moon" then
      drawMoon(ctx, phase, lit, waxing)
    elseif page == "showers" then
      drawShower(ctx, sh[3], shDays, sh[1], sh[2])
    else
      if ec then drawEclipse(ctx, ec, ecDays) else screen.text("NO ECLIPSE", 20, 20, 9, "#6f8793") end
    end
  end
}
