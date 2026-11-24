-- rocket launch pad + launch library 2 upcoming list
local DONE = {Success = true, Failure = true, ["Partial Failure"] = true}
local FLYING = {Go = true, ["In Flight"] = true, Success = true}
local EXACT = {SEC = true, MIN = true, HR = true}
local MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}
local STATUS = {Go = {"GO", "#34c759"}, TBC = {"TBC", "#ffb81c"}, TBD = {"TBD", "#6f8793"},
                Hold = {"HOLD", "#ff3b30"}, ["In Flight"] = {"UP", "#3caaff"}}

-- size 6 advances, most capitals 7 and digits 6
local W6 = {E = 6, F = 6, L = 6, P = 6, S = 6, T = 6, Y = 6, Z = 6, I = 3, J = 4, M = 8, O = 8, Q = 8, W = 10,
            [" "] = 3, [":"] = 3, ["."] = 3, ["-"] = 5, ["/"] = 4, ["+"] = 6}
for d = 0, 9 do W6[tostring(d)] = 6 end

local function width6(s)
  local n = 0
  for i = 1, #s do n = n + (W6[string.sub(s, i, i)] or 7) end
  return n - 1
end

-- whole words while they fit, else letters
local function fit(s, most)
  while width6(s) > most do
    local cut = nil
    for i = #s, 2, -1 do
      if string.sub(s, i, i) == " " then cut = i break end
    end
    if not cut then break end
    s = string.sub(s, 1, cut - 1)
  end
  while #s > 1 and width6(s) > most do s = string.sub(s, 1, #s - 1) end
  return s
end

local function days(y, m, d)
  if m <= 2 then y = y - 1 end
  local era = y // 400
  local yoe = y - era * 400
  local doy = (153 * ((m + 9) % 12) + 2) // 5 + d - 1
  return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468
end

local function epoch(s)
  if type(s) ~= "string" or #s < 19 then return nil end
  local y, mo, d = tonumber(string.sub(s, 1, 4)), tonumber(string.sub(s, 6, 7)), tonumber(string.sub(s, 9, 10))
  local h, mi, se = tonumber(string.sub(s, 12, 13)), tonumber(string.sub(s, 15, 16)), tonumber(string.sub(s, 18, 19))
  if not (y and mo and d and h and mi and se) then return nil end
  return days(y, mo, d) * 86400 + h * 3600 + mi * 60 + se
end

local function offset(ctx)
  local d = ctx.hour * 3600 + ctx.minute * 60 + ctx.second - ctx.epochSec % 86400
  if d > 50400 then d = d - 86400 elseif d < -43200 then d = d + 86400 end
  return (d + 450) // 900 * 900
end

-- the rocket and mission halves of a launch name
local function halves(name)
  for i = 1, #name - 2 do
    if string.sub(name, i, i + 2) == " | " then return string.sub(name, 1, i - 1), string.sub(name, i + 3) end
  end
  return name, ""
end

-- month and day of days since 1970
local function civil(d)
  local z = d + 719468
  local era = z // 146097
  local doe = z - era * 146097
  local yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
  local doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
  local mp = (5 * doy + 2) // 153
  return mp < 10 and mp + 3 or mp - 9, doy - (153 * mp + 2) // 5 + 1
end

local function pad2(n) return n < 10 and ("0" .. n) or tostring(n) end

local function count(sec)
  if sec >= 86400 then return (sec // 86400) .. "D " .. ((sec % 86400) // 3600) .. "H" end
  local h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
  if h > 0 then return h .. ":" .. pad2(m) .. ":" .. pad2(s) end
  return m .. ":" .. pad2(s)
end

local function words(sec)
  if sec >= 86400 then return (sec // 86400) .. "d " .. ((sec % 86400) // 3600) .. "h" end
  if sec >= 3600 then return (sec // 3600) .. "h " .. ((sec % 3600) // 60) .. "m" end
  return ((sec + 59) // 60) .. " min"
end

-- the launch to show, skipping done, scrubbed, and other places
local function pick(now)
  local feed = data.launches
  local v = feed and feed.value
  local list = type(v) == "table" and v.results
  if type(list) ~= "table" then return nil, false end
  for i = 1, #list do
    local r = list[i]
    local net = type(r) == "table" and epoch(r.net)
    local st = type(r) == "table" and type(r.status) == "table" and r.status.abbrev or "TBD"
    local loc = type(r) == "table" and type(r.location) == "string" and r.location or ""
    local here = settings.where ~= "United States" or string.sub(loc, -3) == "USA"
    if net and here and not (DONE[st] and now > net + 600) then
      local late = now - net
      if late < 0 or (late < 600 and FLYING[st]) then
        local rocket, mission = halves(type(r.name) == "string" and r.name or "LAUNCH")
        if type(r.mission) == "string" and r.mission ~= "" then mission = r.mission end
        local prec = type(r.net_precision) == "table" and r.net_precision.abbrev or "MIN"
        return {net = net, status = st, rocket = rocket, mission = mission, exact = EXACT[prec] == true,
                id = tostring(r.id or r.name)}, true
      end
    end
  end
  return nil, true
end

local function stars(ctx)
  for i = 1, 9 do
    local x = 22 + (i * 7) % 12
    local y = 2 + (i * 5) % 10
    if (ctx.monoMs // 350 + i) % 6 ~= 0 then screen.pixel(x, y, "#3a4650") end
  end
end

-- the rocket with its base at y, cut off above the screen
local function rocket(x, base)
  local function px(dx, dy, c) local y = base + dy if y >= 1 then screen.pixel(x + dx, y, c) end end
  px(0, -21, "#c8ced8")
  for dx = -1, 1 do px(dx, -20, "#c8ced8") end
  for dx = -2, 2 do px(dx, -19, "#c8ced8") end
  for dy = -18, -2 do
    local c = dy == -14 and "#2a3a46" or (dy == -8 and "#3caaff" or "#d8dee6")
    for dx = -2, 2 do px(dx, dy, c) end
  end
  for dy = -5, -1 do
    px(-3, dy, "#ff5a3c")
    px(3, dy, "#ff5a3c")
    if dy >= -3 then px(-4, dy, "#ff5a3c") px(4, dy, "#ff5a3c") end
  end
  for dx = -1, 1 do px(dx, 0, "#6f8793") end
end

local function tower(ctx, arms)
  for y = 6, 27 do
    screen.pixel(7, y, "#5a6a74")
    screen.pixel(9, y, "#5a6a74")
    if y % 2 == 0 then screen.pixel(8, y, "#3a4650") end
  end
  if arms then
    for x = 10, 13 do screen.pixel(x, 10, "#5a6a74") screen.pixel(x, 18, "#5a6a74") end
  end
  if (ctx.monoMs // 600) % 2 == 0 then screen.pixel(8, 5, "#ff3b30") end
end

local function ground()
  screen.rect(2, 29, 33, 1, "#3a2e24", true)
  screen.rect(10, 28, 13, 1, "#6f8793", true)
end

local function vapor(ctx)
  for i = 0, 3 do
    local p = (ctx.monoMs // 160 + i * 7) % 24
    local x = 12 + i * 3 + (p // 6) * (i % 2 == 0 and -1 or 1)
    local y = 27 - p // 4
    if y >= 20 then screen.pixel(x, y, p < 12 and "#4a5560" or "#2a3138") end
  end
end

-- flame and smoke s seconds after liftoff
local function liftoff(ctx, s)
  local rise = math.floor(0.45 * s * s + 0.5)
  local base = 27 - rise
  local flick = (ctx.monoMs // 70) % 3
  for k = 1, 3 + flick do
    local y = base + k
    if y >= 1 and y <= 28 then
      local c = k <= 1 and "#fff2a8" or (k <= 3 and "#ffb81c" or "#ff5a1f")
      screen.rect(15, y, 3, 1, c, true)
    end
  end
  local puff = s < 6 and s or 6
  for i = 0, 4 do
    local r = math.floor(1 + puff * (0.4 + 0.1 * i))
    if r > 4 then r = 4 end
    local cx = 16 + (i - 2) * (3 + math.floor(puff))
    if cx - r >= 2 and cx + r <= 34 then screen.circle(cx, 28 - r // 2, r, i % 2 == 0 and "#4a4f55" or "#2f3337") end
  end
  if base - 21 <= 30 then rocket(16, base) end
end

local launchAt = {}

local function sayWait(ctx, words2)
  screen.text("NEXT LAUNCH", 40, 13, 6, "#6f8793")
  local dots = words2 or ("LOADING" .. string.sub("...", 1, (ctx.monoMs // 400) % 4))
  screen.text(dots, 40, 24, 6, "#a1b5bd")
end

return {
  frame = function(ctx)
    local now = ctx.epochSec
    local feed = data.launches
    local l, have = pick(now)
    stars(ctx)
    ground()
    if not l then
      tower(ctx, true)
      rocket(16, 27)
      if have then
        state.next = "No launches"
        sayWait(ctx, "NONE SOON")
      else
        local down = feed and (feed.status == "error" or feed.status == "offline")
        state.next = down and "Offline" or "Waiting for data"
        sayWait(ctx, down and "OFFLINE" or nil)
      end
      return
    end
    local name = string.upper(l.rocket)
    local rest = l.net - now
    local st = STATUS[l.status] or STATUS.TBD
    if rest <= 0 then
      if not launchAt[l.id] then launchAt[l.id] = ctx.monoMs + rest * 1000 end
      local s = (ctx.monoMs - launchAt[l.id]) / 1000
      if s < 0 then s = 0 end
      tower(ctx, false)
      liftoff(ctx, s)
      state.next = l.rocket .. " liftoff"
      screen.text(fit(name, 84), 40, 9, 6, "#6f8793")
      screen.text("LIFTOFF", 40, 22, 11, (ctx.monoMs // 400) % 2 == 0 and "#ffb81c" or "#ffffff")
    else
      tower(ctx, true)
      vapor(ctx)
      rocket(16, 27)
      local sw = width6(st[1])
      screen.text(st[1], 125 - sw, 9, 6, st[2])
      screen.text(fit(name, 82 - sw), 40, 9, 6, "#6f8793")
      if l.exact then
        state.next = l.rocket .. " in " .. words(rest)
        screen.text("T-" .. count(rest), 40, 22, 11, rest < 600 and "#ffb81c" or "#ffffff")
      else
        local m, day = civil((l.net + offset(ctx)) // 86400)
        state.next = l.rocket .. " on " .. string.sub(MONTHS[m], 1, 1) .. string.lower(string.sub(MONTHS[m], 2)) .. " " .. day
        screen.text(MONTHS[m] .. " " .. day, 40, 22, 11, "#ffffff")
      end
    end
    screen.text(fit(string.upper(l.mission), 85), 40, 29, 6, "#3caaff")
    if feed and feed.status ~= "ok" and feed.status ~= nil and feed.status ~= "loading" then
      screen.pixel(125, 2, "#ff9500")
    end
  end
}
