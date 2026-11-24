-- the day's doses at their times + when one is due the bottle opens and a pill hops out until you say you took it +
-- a dot a dose, filled once taken, and the count starts over each day + nothing leaves the board
local DOSES = {["Once a day"] = {0}, ["Twice a day"] = {0, 12}, ["Three times"] = {0, 6, 12}}
local FIRST = {["6 am"] = 6, ["7 am"] = 7, ["8 am"] = 8, ["9 am"] = 9, ["10 am"] = 10}

local function dim(hex, k)
  if k >= 1 then return hex end
  local r, g, b = tonumber(hex:sub(2, 3), 16), tonumber(hex:sub(4, 5), 16), tonumber(hex:sub(6, 7), 16)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function clock(h, c24)
  if c24 then return string.format("%d:00", h) end
  local twelve = (h % 12 == 0) and 12 or h % 12
  return twelve .. (h < 12 and " am" or " pm")
end

local function bottle(k, open, ms)
  local lift = 0
  if open then lift = ({0, 2, 3, 2})[(ms // 150) % 4 + 1] end
  screen.rect(7, 5 - lift, 13, 4, dim("#f5f5f5", k), true)       -- the cap
  screen.rect(8, 9, 11, 1, dim("#c46a00", k), true)              -- the neck
  screen.rect(7, 10, 13, 19, dim("#ff9f1c", k), true)            -- the bottle
  screen.rect(8, 15, 11, 8, dim("#f5e9d6", k), true)             -- its label
  screen.rect(12, 16, 3, 6, dim("#ff3b48", k), true)             -- a cross on it
  screen.rect(10, 18, 7, 2, dim("#ff3b48", k), true)
  if open then
    -- a capsule hops out over the bottle's shoulder and back, 1.2 s a hop
    local t = (ms % 1200) / 1200
    local x = math.floor(14 + 10 * t)
    local y = math.floor(9 - 7 * math.sin(t * math.pi))
    screen.rect(x, y, 2, 2, dim("#ff3b48", k), true)
    screen.rect(x + 2, y, 2, 2, dim("#f5f5f5", k), true)
  end
end

return {
  input = function()
    if input.control == "took" then
      local doses = DOSES[settings.doses] or DOSES["Once a day"]
      state.taken = math.min(#doses, (state.taken or 0) + 1)
    end
  end,
  frame = function(ctx)
    -- the board's date, or the day count before its clock is set
    local today = ctx.year and (ctx.year * 10000 + (ctx.month or 1) * 100 + (ctx.day or 1)) or (ctx.epochSec or 0) // 86400
    if state.day ~= today then state.day, state.taken = today, 0 end
    local first = FIRST[settings.first] or 8
    local doses = DOSES[settings.doses] or DOSES["Once a day"]
    local passed = 0
    for _, add in ipairs(doses) do
      if ctx.hour >= first + add then passed = passed + 1 end
    end
    local taken = state.taken or 0
    state.due = math.max(0, passed - taken)
    state.today = taken .. " of " .. #doses
    if state.due > 0 then
      state.next = "now"
    elseif taken >= #doses then
      state.next = "tomorrow"
    else
      state.next = clock(first + doses[taken + 1], ctx.clock24)
    end
    local k = ctx.night and 0.5 or 1
    bottle(k, state.due > 0, ctx.monoMs)
    if state.due > 0 then
      screen.text("TAKE MEDS", 30, 21, 11, dim("#ffffff", k))
    else
      screen.text("NEXT DOSE", 30, 12, 6, dim("#6f8793", k))
      screen.text(string.upper(state.next), 30, 26, 11, dim("#e6edf0", k))
    end
    for i = 1, #doses do
      local x = 30 + (i - 1) * 6
      screen.rect(x, 28, 4, 2, dim(i <= taken and "#34c759" or "#2a3944", k), true)
    end
  end
}
