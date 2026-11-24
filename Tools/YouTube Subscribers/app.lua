-- YouTube Subscribers: a channel's subscribers, views, or videos from the YouTube Data API with the owner's own key,
-- which the board sends in a header and never in a URL. The channel is an ID or a handle, so one feed asks by ID and
-- the other by handle, each 1 unit of the key's 10,000 a day, about 200 a day together + the board's Lua has no string
-- patterns, so the text helpers walk the characters
local DAY = {
  number = {255, 255, 255}, label = {170, 170, 170}, words = {220, 220, 220}, bell = {64, 210, 190},
  ring = {40, 120, 110}, stale = {255, 149, 0},
}
local ROLL_MS = 1200
local NO_KEY = "configure the source credentials"
local REFUSED = "data source returned an error"
local SHOW = {["Subscribers"] = {"subscriberCount", "subscriber", "SUBSCRIBERS"},
  ["Views"] = {"viewCount", "view", "VIEWS"}, ["Videos"] = {"videoCount", "video", "VIDEOS"}}

local function paint(rgb, ctx, k)
  k = (k or 1) * (ctx.night and 0.45 or 1)
  return (math.floor(rgb[1] * k) << 16) | (math.floor(rgb[2] * k) << 8) | math.floor(rgb[3] * k)
end

local function commas(n)
  local s, out = tostring(n), ""
  for i = 1, #s do
    out = out .. s:sub(i, i)
    if i < #s and (#s - i) % 3 == 0 then out = out .. "," end
  end
  return out
end

-- every digit under a million, then three figures and M or B, cut down and never rounded up, as YouTube does
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

local function trimmed(s)
  s = tostring(s or "")
  local a, b = 1, #s
  while a <= b and s:byte(a) <= 32 do a = a + 1 end
  while b >= a and s:byte(b) <= 32 do b = b - 1 end
  return s:sub(a, b)
end

local function handle(s)
  s = tostring(s)
  if s:sub(1, 1) == "@" then s = s:sub(2) end
  return s:lower()
end

-- an ID matches as it is, and a handle with or without its @ and in any case
local function matches(item, channel)
  if type(item) ~= "table" then return false end
  if item.id == channel then return true end
  local custom = type(item.snippet) == "table" and item.snippet.customUrl
  return type(custom) == "string" and handle(custom) == handle(channel)
end

-- the channel's item and its feed, or nil and whether either feed still holds another channel's answer
local function found(d, channel)
  local other = false
  for _, key in ipairs({"byid", "byhandle"}) do
    local feed = d[key] or {}
    local items = type(feed.value) == "table" and feed.value.items
    if type(items) == "table" and #items > 0 then
      if matches(items[1], channel) then return items[1], feed end
      other = true
    end
  end
  return nil, other
end

local function empty(feed)
  local v = feed.value
  return feed.status == "ok" and type(v) == "table" and (v.items == nil or #v.items == 0)
end

-- the count, its unit, its label, and whether it's stale, or nil and the words to show instead
local function reading()
  local d = type(data) == "table" and data or {}
  local channel = trimmed(settings.channel)
  local show = SHOW[settings.show] or SHOW.Subscribers
  local item, feed = found(d, channel)
  if item then
    local stats = type(item.statistics) == "table" and item.statistics or {}
    if show[1] == "subscriberCount" and (stats.hiddenSubscriberCount == true or stats.subscriberCount == nil) then
      return nil, "Subscribers hidden", {"SUBSCRIBERS", "HIDDEN"}
    end
    local n = tonumber(stats[show[1]])
    if n then return n, show[2], show[3], feed.status ~= nil and feed.status ~= "ok" end
    return nil, "Waiting for YouTube", {"WAITING FOR", "YOUTUBE"}
  end
  local a, b = d.byid or {}, d.byhandle or {}
  if a.error == NO_KEY or b.error == NO_KEY then return nil, "Add your API key", {"ADD YOUR", "API KEY"} end
  if not feed then
    if (empty(a) and (empty(b) or b.error == REFUSED)) or (empty(b) and a.error == REFUSED) then
      return nil, "Channel not found", {"CHANNEL NOT", "FOUND"}
    end
    if a.error == REFUSED and b.error == REFUSED then return nil, "Check your API key", {"CHECK YOUR", "API KEY"} end
  end
  return nil, "Waiting for YouTube", {"WAITING FOR", "YOUTUBE"}
end

-- the store's own mark, a teal bell that swings, its clapper a beat behind, never another brand's logo
local BELL = {{5, 1}, {6, 2}, {7, 3}, {8, 4}, {9, 4}, {10, 5}, {11, 5}, {12, 5}, {13, 5}, {14, 5}, {15, 6}, {16, 6},
  {17, 6}, {18, 7}, {19, 9}, {20, 9}}   -- each row and its half width either side of x 16
local function bell(ctx)
  local ms = ctx.monoMs
  local swing = math.floor(2 * math.sin(ms / 260) + 0.5)
  local lag = math.floor(2 * math.sin(ms / 260 - 0.9) + 0.5)
  local c = paint(DAY.bell, ctx)
  for _, row in ipairs(BELL) do
    local y, half = row[1], row[2]
    screen.rect(16 - half + math.floor(swing * (y - 5) / 15 + 0.5), y, 2 * half, 1, c, true)
  end
  screen.rect(14 + lag, 22, 4, 2, c, true)
  screen.rect(15 + lag, 24, 2, 1, c, true)
  if swing ~= 0 then
    local r, x = paint(DAY.ring, ctx), swing > 0 and 27 or 4
    screen.line(x, 9, x, 12, r)
    screen.line(x + (swing > 0 and -1 or 1), 6, x + (swing > 0 and -1 or 1), 7, r)
  end
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
    bell(ctx)
    local value, unit, label, stale = reading()
    if value == nil then
      state.count = unit
      screen.text(label[1], 33, 14, 8, paint(DAY.words, ctx))
      screen.text(label[2], 33, 25, 8, paint(DAY.words, ctx))
      roll.to = nil
      return
    end
    state.count = short(value) .. " " .. (value == 1 and unit or unit .. "s")
    screen.text(short(rolled(value, ctx.monoMs)), 33, 17, 13, paint(DAY.number, ctx))
    screen.text(label, 33, 27, 6, paint(DAY.label, ctx))
    if stale then screen.pixel(126, 2, paint(DAY.stale, ctx)) end
  end
}
