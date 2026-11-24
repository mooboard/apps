-- uptime + a status light per service
local KEYS = {"one", "two", "three", "four"}
-- size 6 and 9 advances
local W6 = {E = 6, F = 6, L = 6, P = 6, S = 6, T = 6, Y = 6, Z = 6, I = 3, J = 4, M = 8, O = 8, Q = 8, W = 10,
            [" "] = 3, ["."] = 3, ["-"] = 5, ["/"] = 4}
local W9 = {A = 9, B = 9, C = 8, D = 10, E = 7, F = 7, G = 9, H = 10, I = 4, J = 4, K = 8, L = 7, M = 11, N = 9, O = 10,
            P = 8, Q = 10, R = 9, S = 8, T = 8, U = 9, V = 9, W = 14, X = 8, Y = 8, Z = 8,
            [" "] = 3, ["."] = 3, ["-"] = 5, ["/"] = 4}
for d = 0, 9 do W6[tostring(d)] = 6 W9[tostring(d)] = 7 end
-- word, color, rank, and how the readout says it
local LOOK = {
  up = {"UP", {52, 199, 89}, 0},
  updating = {"UPDATING", {60, 170, 255}, 1, " is updating"},
  checking = {"CHECKING", {111, 135, 147}, 1},
  offline = {"NO WI-FI", {58, 70, 80}, 1},
  issues = {"ISSUES", {255, 184, 28}, 2, " has issues"},
  outage = {"OUTAGE", {255, 59, 48}, 3, " has an outage"},
  down = {"DOWN", {255, 59, 48}, 4, " is down"},
}
local INDICATOR = {none = "up", minor = "issues", major = "outage", critical = "outage", maintenance = "updating"}

local function width(s, size)
  local t, n = size == 9 and W9 or W6, 0
  for i = 1, #s do n = n + (t[string.sub(s, i, i)] or (size == 9 and 9 or 7)) end
  return n - 1
end

local function fit(s, size, most)
  while #s > 1 and width(s, size) > most do s = string.sub(s, 1, #s - 1) end
  return s
end

-- a name from a link when the page gives none + its longest part before the last
local function host(url)
  local s = url
  if string.sub(s, 1, 8) == "https://" then s = string.sub(s, 9) end
  for i = 1, #s do
    local ch = string.sub(s, i, i)
    if ch == "/" or ch == ":" or ch == "?" then s = string.sub(s, 1, i - 1) break end
  end
  local parts, from = {}, 1
  for i = 1, #s + 1 do
    if i > #s or string.sub(s, i, i) == "." then
      parts[#parts + 1] = string.sub(s, from, i - 1)
      from = i + 1
    end
  end
  local best
  for i = 1, #parts - 1 do
    local p = parts[i]
    if p ~= "www" and p ~= "api" and p ~= "status" and (best == nil or #p > #best) then best = p end
  end
  best = best or parts[1] or s
  return string.upper(string.sub(best, 1, 1)) .. string.sub(best, 2)
end

local function services()
  local list = {}
  for i = 1, #KEYS do
    local url = settings[KEYS[i]]
    if type(url) == "string" and string.sub(url, 1, 8) == "https://" then list[#list + 1] = {key = KEYS[i], url = url} end
  end
  return list
end

local function judge(ctx, s)
  local feed = data[s.key]
  local v = feed and feed.value
  local name = type(v) == "table" and type(v.page) == "table" and type(v.page.name) == "string" and v.page.name
  s.name = name or host(s.url)
  if not ctx.online or (feed and feed.status == "offline") then return "offline" end
  if not feed or feed.status == "error" then return feed and "down" or "checking" end
  if v == nil then return "checking" end
  local ind = type(v.status) == "table" and v.status.indicator
  return INDICATOR[ind] or "up"
end

local seen, rings = {}, {}

local function ring(ctx, s, cx, cy, rgb, most)
  local feed = data[s.key]
  local at = feed and feed.updatedAt
  if at ~= nil and seen[s.key] ~= nil and at ~= seen[s.key] then rings[s.key] = ctx.monoMs end
  if at ~= nil then seen[s.key] = at end
  local start = rings[s.key]
  if not start then return end
  local t = ctx.monoMs - start
  if t < 0 or t > 700 then rings[s.key] = nil return end
  local r = 3 + t * (most - 3) / 700
  local c = math.floor(rgb[1] * 0.35) * 65536 + math.floor(rgb[2] * 0.35) * 256 + math.floor(rgb[3] * 0.35)
  for k = 0, 11 do
    local a = k * math.pi / 6
    local x, y = cx + math.floor(r * math.cos(a) + 0.5), cy + math.floor(r * math.sin(a) + 0.5)
    if x >= 1 and x <= 126 and y >= 1 and y <= 30 then screen.pixel(x, y, c) end
  end
end

local function light(ctx, kind, cx, cy, r)
  local look = LOOK[kind]
  local rgb = look[2]
  local f = 1
  if kind == "up" then f = 0.7 + 0.3 * math.sin(ctx.monoMs / 900)
  elseif kind == "checking" then f = 0.45 + 0.35 * math.sin(ctx.monoMs / 250)
  elseif look[3] >= 3 then f = (ctx.monoMs // 500) % 2 == 0 and 1 or 0.35 end
  local c = math.floor(rgb[1] * f) * 65536 + math.floor(rgb[2] * f) * 256 + math.floor(rgb[3] * f)
  screen.circle(cx, cy, r, c)
  return rgb
end

local function hex(rgb)
  return rgb[1] * 65536 + rgb[2] * 256 + rgb[3]
end

return {
  frame = function(ctx)
    local list = services()
    if #list == 0 then
      state.status = "No services"
      screen.text("ADD A SERVICE", 64 - width("ADD A SERVICE", 6) // 2, 14, 6, "#a1b5bd")
      screen.text("IN THE APP", 64 - width("IN THE APP", 6) // 2, 25, 6, "#6f8793")
      return
    end
    local worst, worstName, ups, kinds = nil, nil, 0, {}
    for i = 1, #list do
      local s = list[i]
      local kind = judge(ctx, s)
      kinds[i] = kind
      if kind == "up" then ups = ups + 1 end
      if LOOK[kind][4] and (worst == nil or LOOK[kind][3] > LOOK[worst][3]) then worst, worstName = kind, s.name end
    end
    if not ctx.online then state.status = "Board offline"
    elseif ups == #list then state.status = "All up"
    elseif worst then state.status = worstName .. LOOK[worst][4]
    else state.status = "Checking" end
    if #list <= 2 then
      for i = 1, #list do
        local s, kind = list[i], kinds[i]
        local cy = #list == 1 and 16 or (i == 1 and 8 or 23)
        local rgb = light(ctx, kind, 8, cy, 3)
        ring(ctx, s, 8, cy, rgb, 8)
        local word = LOOK[kind][1]
        local ww = width(word, 6)
        screen.text(word, 125 - ww, cy + 3, 6, hex(rgb))
        screen.text(fit(string.upper(s.name), 9, 104 - ww), 16, cy + 5, 9, "#ffffff")
      end
      return
    end
    -- three or four get smaller rows
    local lines = #list == 3 and {9, 19, 29} or {8, 15, 22, 29}
    for i = 1, #list do
      local s, kind = list[i], kinds[i]
      local base = lines[i]
      local rgb = light(ctx, kind, 5, base - 3, 2)
      ring(ctx, s, 5, base - 3, rgb, 4.5)
      local word = LOOK[kind][1]
      local ww = width(word, 6)
      screen.text(word, 125 - ww, base, 6, hex(rgb))
      screen.text(fit(string.upper(s.name), 6, 110 - ww), 11, base, 6, "#ffffff")
    end
  end
}
