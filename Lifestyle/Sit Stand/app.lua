-- a calm reminder to switch between sitting and standing every N minutes in the active hours + when it's time the
-- figure gets up from its chair, or sits back down + nothing leaves the board
local EVERY = {["20 min"] = 20, ["30 min"] = 30, ["45 min"] = 45, ["1 hour"] = 60, ["90 min"] = 90}
local HOURS = {["All day"] = false, ["7 am to 7 pm"] = {7, 19}, ["8 am to 6 pm"] = {8, 18},
               ["8 am to 10 pm"] = {8, 22}, ["9 am to 5 pm"] = {9, 17}}
local SNOOZE = 10 * 60
local LOOKS = {
  Gentle = {body = "#d9a441", skin = "#d8cbb8", chair = "#5f7682", floor = "#2a3944", label = "#5f7682", text = "#9fb4c0"},
  Bold = {body = "#ffb81c", skin = "#f5e9d6", chair = "#a1b5bd", floor = "#3a4a55", label = "#a1b5bd", text = "#ffffff"},
  Rest = {body = "#4a4030", skin = "#4a4540", chair = "#2a3944", floor = "#1d2a33", label = "#2a3944", text = "#4a5a66"},
}
-- head, shoulder, hip, knee, foot, and hand, each as x and y
local SIT = {16, 12, 16, 15, 16, 20, 21, 20, 21, 26, 20, 18}
local STAND = {20, 6, 20, 9, 20, 16, 20, 21, 20, 26, 22, 14}
local now = 0

local function resting(ctx)
  if settings.night ~= false and ctx.night then return "night" end
  local h = HOURS[settings.hours]
  if h and not (ctx.hour >= h[1] and ctx.hour < h[2]) then return "off hours" end
  return nil
end

local function words(sec)
  local m = math.ceil(sec / 60)
  if m >= 60 then return (m // 60) .. "h" .. (m % 60 == 0 and "" or (" " .. (m % 60) .. "m")) end
  return m .. " min"
end

local function figure(from, to, p, look)
  -- the pose p of the way from one to the other, 0 to 1
  local q = {}
  for i = 1, #from do q[i] = math.floor(from[i] + (to[i] - from[i]) * p + 0.5) end
  screen.rect(8, 27, 20, 1, look.floor, true)
  screen.rect(11, 21, 7, 1, look.chair, true)    -- the seat
  screen.rect(11, 15, 1, 12, look.chair, true)   -- the back, down to the floor
  screen.rect(17, 22, 1, 5, look.chair, true)    -- the front leg
  screen.line(q[3], q[4], q[5], q[6], look.body)
  screen.line(q[3] + 1, q[4], q[5] + 1, q[6], look.body)
  screen.line(q[5], q[6], q[7], q[8], look.body)
  screen.line(q[7], q[8], q[9], q[10], look.body)
  screen.line(q[3], q[4] + 1, q[11], q[12], look.body)
  screen.circle(q[1], q[2], 2, look.skin)
end

local function ease(p)
  return p * p * (3 - 2 * p)
end

local function words_on(look, line)
  screen.text(state.standing and "STANDING" or "SITTING", 34, 13, 6, look.label)
  screen.text(line, 34, 25, 9, look.text)
end

return {
  start = function()
    state.standing = state.standing or false
  end,
  input = function()
    if input.control == "switched" then
      state.standing = not state.standing
      state.at, state.snooze = now, 0
    elseif input.control == "snooze" then
      state.snooze = now + SNOOZE
    end
  end,
  frame = function(ctx)
    now = ctx.epochSec
    if state.standing == nil then state.standing = false end
    if not state.at or state.at > now then state.at = now end
    state.posture = state.standing and "standing" or "sitting"
    local here = state.standing and STAND or SIT
    local mins = EVERY[settings.every] or 45
    local look = LOOKS[settings.style] or LOOKS.Gentle
    local rest = resting(ctx)
    if rest then
      -- the next reminder comes a full interval after the rest ends
      state.at, state.snooze, state.next = now, 0, rest
      figure(here, here, 0, LOOKS.Rest)
      words_on(LOOKS.Rest, string.upper(rest))
      return
    end
    local due_at = state.at + mins * 60
    local left = math.max(due_at - now, (state.snooze or 0) - now)
    if left <= 0 then
      -- 2 s to get up (or sit down), 2 s there, then again
      state.next = "now"
      local there = state.standing and SIT or STAND
      figure(here, there, ease(math.min(1, (ctx.monoMs % 4000) / 2000)), look)
      words_on(look, state.standing and "SIT DOWN" or "STAND UP")
    elseif now >= due_at then
      state.next = "snoozed"
      figure(here, here, 0, look)
      words_on(look, "SNOOZED")
    else
      state.next = words(left)
      figure(here, here, 0, look)
      words_on(look, "IN " .. string.upper(words(left)))
    end
  end
}
