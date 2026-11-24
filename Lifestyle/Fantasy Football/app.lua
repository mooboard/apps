-- your Sleeper matchup this week, both scores live during games, from api.mooboard.co/fantasy/sleeper, which reads
-- Sleeper's public api with no key (a board's feed url has no week in it and a league's rosters are over 16 KB)
-- + the board's Lua leaves out find, match, and gsub, so names are walked a byte at a time
local SETUP = "your name"
local PAGE_MS, BANNER_MS, FLASH_MS = 8000, 2000, 3000
local LIVE_SEC = 15 * 60       -- live while a score moved in the last 15 min
local BAR_X, BAR_W = 3, 68
local LABEL_X = 76

local C = {
  me = {255, 255, 255}, them = {161, 181, 189}, lead = {255, 255, 255}, trail = {111, 135, 147},
  flash = {52, 199, 89}, mine = {60, 170, 255}, theirs = {58, 70, 80}, live = {255, 59, 48},
  label = {111, 135, 147}, league = {255, 184, 28}, ball = {139, 74, 31}, lace = {230, 230, 230},
  words = {255, 255, 255}, quiet = {161, 181, 189}, stale = {255, 149, 0},
}

local seen, flash = {}, {}

local function paint(rgb, ctx)
  local k = ctx.night and 0.45 or 1
  return (math.floor(rgb[1] * k) << 16) | (math.floor(rgb[2] * k) << 8) | math.floor(rgb[3] * k)
end

local function trim(s)
  s = tostring(s or "")
  local a, b = 1, #s
  while a <= b and string.sub(s, a, a) == " " do a = a + 1 end
  while b >= a and string.sub(s, b, b) == " " do b = b - 1 end
  return string.sub(s, a, b)
end

local function hasSpace(s)
  for i = 1, #s do
    if string.sub(s, i, i) == " " then return true end
  end
  return false
end

local function cut(s, n)
  s = string.upper(tostring(s or ""))
  if #s > n then s = string.sub(s, 1, n) end
  return s
end

local function num(p) return string.format("%.1f", tonumber(p) or 0) end

-- a score's width at size 9: 7 a digit, 3 the point, 6 a minus
local function width(s)
  local w = 0
  for i = 1, #s do
    local c = string.sub(s, i, i)
    w = w + (c == "." and 3 or (c == "-" and 6 or 7))
  end
  return w
end

local function football(ctx)
  for dy = -5, 5 do
    local w = math.floor(10 * math.sqrt(1 - (dy / 6) ^ 2))
    screen.rect(16 - w, 16 + dy, 2 * w + 1, 1, paint(C.ball, ctx), true)
  end
  screen.rect(11, 16, 11, 1, paint(C.lace, ctx), true)
  for x = 12, 20, 2 do screen.rect(x, 15, 1, 3, paint(C.lace, ctx), true) end
end

local function message(ctx, big, small)
  football(ctx)
  if small then
    screen.text(big, 34, 14, 8, paint(C.words, ctx))
    screen.text(small, 34, 25, small == "SLEEPER NAME" and 8 or 6, paint(C.quiet, ctx))
  else
    screen.text(big, 34, 20, 8, paint(C.words, ctx))
  end
end

-- a team's line: its name, then its score right at x 124 over a dark gap so a long name never runs into it
local function line(ctx, base, name, nameRgb, score, scoreRgb)
  screen.text(cut(name, 24), 3, base, 8, paint(nameRgb, ctx))
  local x = 125 - width(score)
  screen.rect(x - 4, base - 9, 132 - x, 11, 0, true)
  screen.text(score, x, base, 9, paint(scoreRgb, ctx))
end

local function scoreColor(key, mine, other, ctx)
  if flash[key] and ctx.monoMs < flash[key] then return C.flash end
  return mine >= other and C.lead or C.trail
end

local function remember(key, points, ctx)
  if seen[key] ~= nil and seen[key] ~= points then flash[key] = ctx.monoMs + FLASH_MS end
  seen[key] = points
end

local function readout(l, final)
  if not l.them then return "Bye week" end
  local a, b = tonumber(l.me.points) or 0, tonumber(l.them.points) or 0
  local word
  if a == b then word = "Tied"
  elseif final then word = a > b and "Won" or "Lost"
  else word = a > b and "Up" or "Down" end
  return word .. " " .. num(a) .. " to " .. num(b)
end

local function matchup(ctx, v, now)
  local list = v.leagues
  local names, sig = {}, ""
  for i = 1, #list do
    local l = list[i]
    names[#names + 1] = tostring(l.name or "")
    local m, t = type(l.me) == "table" and l.me.points, type(l.them) == "table" and l.them.points
    sig = sig .. tostring(l.id) .. ":" .. tostring(m) .. ":" .. tostring(t) .. ";"
  end
  local list_ = ""
  for i = 1, #names do list_ = list_ .. (i > 1 and ", " or "") .. names[i] end
  state.leagues = list_
  local week = tonumber(v.week) or 0
  if sig ~= state.sig then
    if state.sig ~= nil and state.wk == week then state.moved = now end
    state.sig, state.wk = sig, week
  end
  local final = v.final == true
  local live = not final and state.moved ~= nil and now - state.moved < LIVE_SEC

  local page = (ctx.monoMs // PAGE_MS) % #list + 1
  local l = list[page]
  local me = type(l.me) == "table" and l.me or {}
  local them = type(l.them) == "table" and l.them or nil
  local a = tonumber(me.points) or 0
  local b = them and (tonumber(them.points) or 0) or 0
  remember(tostring(l.id) .. "m", a, ctx)
  if them then remember(tostring(l.id) .. "t", b, ctx) end
  state.score = readout({me = me, them = them}, final)

  line(ctx, 11, me.team, C.me, num(a), them and scoreColor(tostring(l.id) .. "m", a, b, ctx) or C.lead)
  if them then
    line(ctx, 28, them.team, C.them, num(b), scoreColor(tostring(l.id) .. "t", b, a, ctx))
  else
    screen.text("BYE WEEK", 3, 28, 8, paint(C.trail, ctx))
  end

  if #list > 1 and ctx.monoMs % PAGE_MS < BANNER_MS then
    screen.text(cut(l.name, 14), BAR_X, 19, 6, paint(C.league, ctx))
  elseif them then
    local share = a + b > 0 and math.floor(BAR_W * a / (a + b) + 0.5) or BAR_W // 2
    screen.rect(BAR_X, 15, BAR_W, 2, paint(C.theirs, ctx), true)
    if share > 0 then screen.rect(BAR_X, 15, share, 2, paint(C.mine, ctx), true) end
  end
  if live then
    if ctx.monoMs % 1000 < 700 then screen.text("LIVE", LABEL_X, 19, 6, paint(C.live, ctx)) end
  elseif final then
    screen.text("FINAL", LABEL_X, 19, 6, paint(C.label, ctx))
  elseif week > 0 then
    screen.text("WEEK " .. week, LABEL_X, 19, 6, paint(C.label, ctx))
  end
end

return {
  frame = function(ctx)
    local user = trim(settings.user)
    local feed = data.ff or {}
    local v = feed.value
    local now = tonumber(ctx.epochSec) or 0
    if user == "" or user == SETUP or hasSpace(user) then
      state.score, state.leagues = "Add your Sleeper name", "None"
      message(ctx, "ADD YOUR", "SLEEPER NAME")
      return
    end
    if type(v) ~= "table" or string.lower(tostring(v.user or "")) ~= string.lower(user) then
      state.score, state.leagues = "Waiting", "None"
      football(ctx)
      local dots = math.floor(ctx.monoMs / 400) % 4
      screen.text("FANTASY" .. string.sub("...", 1, dots), 34, 20, 9, paint(C.quiet, ctx))
      return
    end
    if v.error == "user" then
      state.score, state.leagues = "No such Sleeper user", "None"
      message(ctx, "NO SUCH USER", cut(user, 16))
    elseif v.error == "league" then
      state.score, state.leagues = "No such league", "None"
      message(ctx, "NO LEAGUE", cut(trim(settings.league), 16))
    elseif v.off then
      state.score, state.leagues = "Off season", "None"
      message(ctx, "OFF SEASON")
    elseif type(v.leagues) ~= "table" or #v.leagues == 0 then
      state.score, state.leagues = "No leagues this season", "None"
      message(ctx, "NO LEAGUES", tostring(v.season or ""))
    else
      matchup(ctx, v, now)
    end
    if feed.status ~= nil and feed.status ~= "ok" then screen.pixel(126, 2, paint(C.stale, ctx)) end
  end
}
