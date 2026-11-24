-- GitHub Counter: followers from the public profile, a repo's stars from the public search API (owner/name in one
-- setting, so org repos work too), or the contribution streak from mooboard's cached GitHub Grid feed. No key, and at
-- most 6 calls an hour to GitHub (60 an hour per address for the core API, 10 a minute for search) + the board's Lua has
-- no string patterns, so the text helpers walk the characters
local DAY = {
  number = {255, 255, 255}, label = {139, 148, 158}, words = {201, 209, 217}, person = {201, 209, 217},
  back = {120, 128, 138}, green = {63, 185, 80}, gold = {255, 200, 40}, spark = {255, 244, 200},
  outer = {255, 90, 20}, flame = {255, 160, 40}, core = {255, 230, 140}, stale = {255, 149, 0},
}
local ROLL_MS = 1200

local function paint(rgb, ctx, k)
  k = (k or 1) * (ctx.night and 0.45 or 1)
  return (math.floor(rgb[1] * k) << 16) | (math.floor(rgb[2] * k) << 8) | math.floor(rgb[3] * k)
end

-- size 6's advances on the board (nunito's and a dot between letters) for the label, and 7 for any other capital or
-- byte so a guess is never short
local W6 = {[" "] = 3, [","] = 3, ["-"] = 5, ["."] = 3, ["/"] = 4, ["_"] = 5, I = 3, J = 4, M = 8, O = 8, Q = 8, W = 10,
  E = 6, F = 6, L = 6, P = 6, S = 6, T = 6, Y = 6, Z = 6}
local function width6(s)
  local w = 0
  for i = 1, #s do
    local c = s:sub(i, i)
    w = w + (W6[c] or ((c >= "0" and c <= "9") and 6) or 7)
  end
  return w
end
local function fit6(s, room)
  while #s > 0 and width6(s) > room do s = s:sub(1, -2) end
  return s
end

local function commas(n)
  local s, out = tostring(n), ""
  for i = 1, #s do
    out = out .. s:sub(i, i)
    if i < #s and (#s - i) % 3 == 0 then out = out .. "," end
  end
  return out
end

-- every digit under a million, then three figures and M or B, cut down and never rounded up
local function short(n)
  n = math.max(0, math.floor(n))
  if n < 1000000 then return commas(n) end
  local unit, base = "M", 1000000
  if n >= 1000000000 then unit, base = "B", 1000000000 end
  local s
  if n < 10 * base then
    local h = n // (base // 100)
    local whole, part = h // 100, h % 100
    s = part == 0 and tostring(whole) or part % 10 == 0 and (whole .. "." .. part // 10) or
      string.format("%d.%02d", whole, part)
  elseif n < 100 * base then
    local t = n // (base // 10)
    s = t % 10 == 0 and tostring(t // 10) or (t // 10 .. "." .. t % 10)
  else s = tostring(n // base) end
  return s .. unit
end

local function same(a, b)
  return type(a) == "string" and type(b) == "string" and a:lower() == b:lower()
end

-- a setting without spaces at its ends or an @ in front
local function trimmed(s)
  s = tostring(s or "")
  local a, b = 1, #s
  while a <= b and s:byte(a) <= 32 do a = a + 1 end
  while b >= a and s:byte(b) <= 32 do b = b - 1 end
  if s:sub(a, a) == "@" then a = a + 1 end
  return s:sub(a, b)
end

-- the name after owner/, or nil unless there's exactly one slash with words on both sides
local function repoName(repo)
  local at, slashes = 0, 0
  for i = 1, #repo do
    if repo:sub(i, i) == "/" then at, slashes = i, slashes + 1 end
  end
  if slashes ~= 1 or at == 1 or at == #repo then return nil end
  return repo:sub(at + 1)
end

-- days in a row with a contribution up to today, or up to yesterday while today is still empty
local function streak(levels)
  local n, at = 0, #levels
  if levels:sub(at, at) == "0" then at = at - 1 end
  while at > 0 and levels:sub(at, at) ~= "0" do n, at = n + 1, at - 1 end
  return n
end

-- the count, its unit, and its label, or nil and the words to show instead
local function reading()
  local d = type(data) == "table" and data or {}
  local user, show = trimmed(settings.user), settings.show
  local feed, value, unit, label, refused
  if show == "Stars" then
    local repo = trimmed(settings.repo)
    local name = repoName(repo)
    if not name then return nil, "Use owner/name for the repo", {"REPO IS", "OWNER/NAME"} end
    feed = d.repo or {}
    local v = feed.value
    if type(v) == "table" and type(v.items) == "table" then
      local item = v.items[1]
      if type(item) == "table" and same(item.full_name, repo) and type(item.stargazers_count) == "number" then
        value, unit = item.stargazers_count, "star"
        label = fit6(string.upper(name), 92)   -- the star says stars, so the label is the repo
      elseif #v.items == 0 and v.total_count == 0 and feed.status == "ok" then
        return nil, "Repo not found", {"REPO NOT", "FOUND"}
      end
    end
    refused = "Check the repo"
  elseif show == "Streak" then
    feed = d.days or {}
    local v = feed.value
    if type(v) == "table" and same(v.user, user) and type(v.levels) == "string" and v.levels ~= "" then
      value, unit, label = streak(v.levels), "day streak", "DAY STREAK"
    end
    refused = "Check the username"
  else
    feed = d.user or {}
    local v = feed.value
    if type(v) == "table" and same(v.login, user) and type(v.followers) == "number" then
      value, unit, label = v.followers, "follower", "FOLLOWERS"
    end
    refused = "Check the username"
  end
  if value ~= nil then return value, unit, label, feed.status ~= nil and feed.status ~= "ok" end
  if feed.error == "data source returned an error" then
    return nil, refused, refused == "Check the repo" and {"CHECK THE", "REPO"} or {"CHECK THE", "USERNAME"}
  end
  return nil, "Waiting for GitHub", {"WAITING FOR", "GITHUB"}
end

-- someone and the one behind them, round heads and shoulders, and a green plus rises over them now and then
local function person(cx, c)
  screen.rect(cx - 1, 7, 3, 1, c, true)
  screen.rect(cx - 2, 8, 5, 3, c, true)
  screen.rect(cx - 1, 11, 3, 1, c, true)
  screen.rect(cx - 2, 14, 5, 1, c, true)
  screen.rect(cx - 3, 15, 7, 1, c, true)
  screen.rect(cx - 4, 16, 9, 6, c, true)
end
local function followers(ctx)
  person(20, paint(DAY.back, ctx))
  person(12, paint(DAY.person, ctx))
  local t = ctx.monoMs % 3000
  if t < 1500 then
    local y = 9 - t // 300
    local g = paint(DAY.green, ctx, 1 - t / 3000)
    screen.line(24, y, 26, y, g)
    screen.line(25, y - 1, 25, y + 1, g)
  end
end

-- a gold star from the Home icon's drawing at 2x, as runs worked out once, with a spark going round it
local STAR = {
  ".....##.....",
  ".....##.....",
  "....####....",
  ".##########.",
  "..########..",
  "...######...",
  "...######...",
  "..###..###..",
  "..##....##..",
  ".##......##.",
}
local RUNS = {}
for row = 1, #STAR do
  local line, x = STAR[row], 1
  while x <= #line do
    if line:sub(x, x) == "#" then
      local stop = x
      while stop < #line and line:sub(stop + 1, stop + 1) == "#" do stop = stop + 1 end
      RUNS[#RUNS + 1] = {3 + 2 * (x - 1), 3 + 2 * row, 2 * (stop - x + 1)}
      x = stop + 1
    else
      x = x + 1
    end
  end
end
local function stars(ctx)
  local glow = 0.85 + 0.15 * math.sin(ctx.monoMs / 400)
  local c = paint(DAY.gold, ctx, glow)
  for _, run in ipairs(RUNS) do screen.rect(run[1], run[2], run[3], 2, c, true) end
  local spots = {{3, 4}, {26, 4}, {26, 25}, {3, 25}}
  local spot = spots[(ctx.monoMs // 500) % 4 + 1]
  local s = paint(DAY.spark, ctx)
  screen.pixel(spot[1], spot[2], s)
  screen.pixel(spot[1] - 1, spot[2], paint(DAY.spark, ctx, 0.4))
  screen.pixel(spot[1] + 1, spot[2], paint(DAY.spark, ctx, 0.4))
  screen.pixel(spot[1], spot[2] - 1, paint(DAY.spark, ctx, 0.4))
  screen.pixel(spot[1], spot[2] + 1, paint(DAY.spark, ctx, 0.4))
end

-- a flame in three colors, its tip swaying and its tongues flickering
local function tongue(mid, top, bottom, half, sway, c)
  for y = top, bottom do
    local w = math.floor((y - top) * half / (bottom - top) + 0.5)
    local x = mid + math.floor(sway * (bottom - y) / (bottom - top) + 0.5)
    screen.line(x - w, y, x + w, y, c)
  end
end
local function flame(ctx)
  local ms = ctx.monoMs
  local sway = math.floor(2 * math.sin(ms / 170) + 0.5)
  local outer, mid, core = paint(DAY.outer, ctx), paint(DAY.flame, ctx), paint(DAY.core, ctx)
  screen.circle(15, 20, 6, outer)
  tongue(15, 5, 20, 6, sway, outer)
  tongue(10, 10 + (ms // 140) % 3, 17, 2, -1, outer)
  tongue(20, 12 - (ms // 110) % 3, 17, 2, 1, outer)
  screen.circle(15, 21, 4, mid)
  tongue(15, 11, 21, 4, sway // 2, mid)
  screen.circle(15, 23, 2, core)
  screen.line(15, 18 + (ms // 120) % 2, 15, 23, core)
end

local roll = {from = 0, to = nil, at = 0}
local function rolled(target, now)
  if roll.to ~= target then
    local shown = roll.to and roll.from + (roll.to - roll.from) * math.min(1, (now - roll.at) / ROLL_MS) or 0
    roll.from, roll.to, roll.at = shown, target, now
  end
  local t = math.min(1, math.max(0, (now - roll.at) / ROLL_MS))
  return roll.from + (target - roll.from) * (1 - (1 - t) ^ 3)
end

return {
  frame = function(ctx)
    local show = settings.show
    if show == "Stars" then stars(ctx) elseif show == "Streak" then flame(ctx) else followers(ctx) end
    local value, unit, label, stale = reading()
    if value == nil then
      state.count = unit
      screen.text(label[1], 33, 14, 8, paint(DAY.words, ctx))
      screen.text(label[2], 33, 25, 8, paint(DAY.words, ctx))
      roll.to = nil
      return
    end
    local plural = (value == 1 or unit == "day streak") and unit or unit .. "s"
    state.count = short(value) .. " " .. plural
    screen.text(short(rolled(value, ctx.monoMs)), 33, 17, 13, paint(DAY.number, ctx))
    screen.text(label, 33, 27, 6, paint(DAY.label, ctx))
    if stale then screen.pixel(126, 2, paint(DAY.stale, ctx)) end
  end
}
