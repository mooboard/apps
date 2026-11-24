-- a calm reminder to drink water every N minutes in the active hours + the glass empties as the time runs, and fills
-- when it's time + nothing leaves the board
local EVERY = {["20 min"] = 20, ["30 min"] = 30, ["45 min"] = 45, ["1 hour"] = 60, ["90 min"] = 90, ["2 hours"] = 120}
local HOURS = {["All day"] = false, ["7 am to 7 pm"] = {7, 19}, ["8 am to 6 pm"] = {8, 18},
               ["8 am to 10 pm"] = {8, 22}, ["9 am to 5 pm"] = {9, 17}}
local SNOOZE = 10 * 60
local LOOKS = {
  Gentle = {water = "#2f8fd8", drop = "#5aa6dc", edge = "#5f7682", label = "#5f7682", text = "#9fb4c0"},
  Bold = {water = "#3caaff", drop = "#9fd8ff", edge = "#a1b5bd", label = "#a1b5bd", text = "#ffffff"},
  Rest = {water = "#1d3a52", drop = "#1d3a52", edge = "#2a3944", label = "#2a3944", text = "#4a5a66"},
}
local GX, GY = 10, 8   -- the glass's corner
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

local function glass(fill, look)
  -- 12 wide and 16 tall, a little narrower at the foot, filled from the bottom 0 to 1 + gives the water's top row
  for row = 0, 15 do
    local w = 12 - row // 5
    local x0 = GX + (12 - w) // 2
    screen.pixel(x0, GY + row, look.edge)
    screen.pixel(x0 + w - 1, GY + row, look.edge)
  end
  screen.rect(GX + 2, GY + 15, 8, 1, look.edge, true)
  local h = math.floor(fill * 14 + 0.5)
  for row = 0, h - 1 do
    local yy = GY + 14 - row
    local w = 12 - (yy - GY) // 5
    local x0 = GX + (12 - w) // 2
    screen.rect(x0 + 1, yy, w - 2, 1, look.water, true)
  end
  return GY + 14 - h
end

local function pour(ctx, look)
  -- 3 s to fill and 1 s full, then again, from a thin stream
  local fill = math.min(1, (ctx.monoMs % 4000) / 3000)
  local top = glass(fill, look)
  if fill < 1 then
    for y = 3, top do screen.pixel(GX + 6, y, look.drop) end
  end
end

local function words_on(look, line)
  screen.text("WATER", 34, 13, 6, look.label)
  screen.text(line, 34, 25, 9, look.text)
end

return {
  input = function()
    if input.control == "drank" then
      state.at, state.snooze = now, 0
    elseif input.control == "snooze" then
      state.snooze = now + SNOOZE
    end
  end,
  frame = function(ctx)
    now = ctx.epochSec
    if not state.at or state.at > now then state.at = now end
    local mins = EVERY[settings.every] or 60
    local look = LOOKS[settings.style] or LOOKS.Gentle
    local rest = resting(ctx)
    if rest then
      -- the next reminder comes a full interval after the rest ends
      state.at, state.snooze, state.next = now, 0, rest
      glass(0.4, LOOKS.Rest)
      words_on(LOOKS.Rest, string.upper(rest))
      return
    end
    local due_at = state.at + mins * 60
    local left = math.max(due_at - now, (state.snooze or 0) - now)
    if left <= 0 then
      state.next = "now"
      pour(ctx, look)
      words_on(look, "DRINK UP")
    elseif now >= due_at then
      state.next = "snoozed"
      glass(0, look)
      words_on(look, "SNOOZED")
    else
      state.next = words(left)
      glass(math.max(0, math.min(1, left / (mins * 60))), look)
      words_on(look, "IN " .. string.upper(words(left)))
    end
  end
}
