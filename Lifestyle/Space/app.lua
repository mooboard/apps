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
-- year, month, day, kind
local ECLIPSES = {
  {2027, 2, 6, "RING SOLAR"}, {2027, 8, 2, "TOTAL SOLAR"}, {2028, 1, 12, "PART LUNAR"},
  {2028, 1, 26, "RING SOLAR"}, {2028, 7, 6, "PART LUNAR"}, {2028, 7, 22, "TOTAL SOLAR"},
  {2028, 12, 31, "TOTAL LUNAR"}, {2029, 1, 14, "PART SOLAR"}, {2029, 6, 12, "PART SOLAR"},
  {2029, 6, 26, "TOTAL LUNAR"}, {2029, 7, 11, "PART SOLAR"}, {2029, 12, 5, "PART SOLAR"},
  {2029, 12, 20, "TOTAL LUNAR"}, {2030, 6, 1, "RING SOLAR"}, {2030, 6, 15, "PART LUNAR"},
  {2030, 11, 25, "TOTAL SOLAR"},
}

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

local function nextEclipse(y, m, d)
  local today = dayno(y, m, d)
  for i = 1, #ECLIPSES do
    local e = ECLIPSES[i]
    local days = dayno(e[1], e[2], e[3]) - today
    if days >= 0 then return e, days end
  end
  return nil
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

local function pages()
  local list = {}
  if settings.iss then list[#list + 1] = "iss" end
  if settings.showers then list[#list + 1] = "showers" end
  if settings.eclipses then list[#list + 1] = "eclipses" end
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
    local ec, ecDays = nextEclipse(ctx.year, ctx.month, ctx.day)
    state.eclipse = ec and (ec[4] .. " " .. ecDays) or "none"
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
    elseif page == "showers" then
      drawShower(ctx, sh[3], shDays, sh[1], sh[2])
    else
      if ec then drawEclipse(ctx, ec, ecDays) else screen.text("NO ECLIPSE", 20, 20, 9, "#6f8793") end
    end
  end
}
