-- a sprout in a pot that asks you to water your real plant every few days + it droops and yellows as the day comes,
-- perks up when you water it, and grows a leaf pair a week + nothing leaves the board
local EVERY = {["2 days"] = 2, ["3 days"] = 3, ["5 days"] = 5, ["1 week"] = 7, ["10 days"] = 10, ["2 weeks"] = 14}
local DAY = 86400
local LOOKS = {   -- leaf, stem
  happy = {"#5fd36e", "#34c759"},
  thirsty = {"#a8c850", "#8fb048"},
  wilting = {"#c8a03c", "#9a7a3a"},
}
local now, splash, pour = 0, false, nil
local SX, SOIL = 16, 21   -- the stem's column and the soil's row

local function rgb(hex)
  return tonumber(hex:sub(2, 3), 16) or 200, tonumber(hex:sub(4, 5), 16) or 100, tonumber(hex:sub(6, 7), 16) or 60
end

local function dim(hex, k)
  if k >= 1 then return hex end
  local r, g, b = rgb(hex)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function pot(k)
  local color = dim(settings.pot or "#C8643C", k)
  screen.rect(8, SOIL, 17, 1, dim("#5a3820", k), true)
  screen.rect(7, 22, 19, 2, color, true)
  for row = 0, 6 do
    local inset = row // 3
    screen.rect(8 + inset, 24 + row, 17 - inset * 2, 1, color, true)
  end
end

local function leaf(x, y, side, droop, big, color)
  -- one leaf off the stem at (x, y), side -1 left or 1 right, droop 0 up, 1 flat, 2 down
  local rise = ({-1, 0, 1})[droop + 1]
  screen.pixel(x + side, y, color)
  screen.pixel(x + side * 2, y + rise, color)
  screen.pixel(x + side * 3, y + rise, color)
  screen.pixel(x + side * 2, y + (droop == 2 and 0 or -1) + (droop == 1 and 1 or 0), color)
  if big then screen.pixel(x + side * 4, y + rise * 2, color) end
end

local function plant(stage, mood, ctx, k)
  local look = LOOKS[mood]
  local leafc, stemc = dim(look[1], k), dim(look[2], k)
  local droop = mood == "happy" and 0 or mood == "thirsty" and 1 or 2
  local sway = mood == "happy" and math.floor(math.sin(ctx.monoMs / 900) + 0.5) or 0
  local h = 3 + stage * 3
  local top_x = SX
  for i = 0, h - 1 do
    local x = SX + ((i > h // 2) and sway or 0) + ((droop == 2 and i > h - 4) and 1 or 0)
    screen.pixel(x, SOIL - 1 - i, stemc)
    top_x = x
  end
  for j = 1, stage do
    local y = SOIL - 1 - j * 3
    local x = SX + ((j * 3 > h // 2) and sway or 0)
    leaf(x, y, -1, droop, j < stage, leafc)
    leaf(x, y - 1, 1, droop, j < stage, leafc)
  end
  -- the bud on top, bowed when it wilts
  local ty = SOIL - h
  if droop == 2 then
    screen.pixel(top_x + 1, ty + 1, leafc)
    screen.pixel(top_x + 2, ty + 2, leafc)
  else
    screen.pixel(top_x - 1, ty, leafc)
    screen.pixel(top_x + 1, ty, leafc)
    screen.pixel(top_x, ty - 1, leafc)
  end
end

local function watering(ms, k)
  local can = dim("#8aa0ad", k)
  screen.rect(28, 3, 7, 5, can, true)
  screen.line(27, 5, 24, 8, can)
  screen.line(35, 4, 36, 6, can)
  for i = 0, 3 do
    local y = 10 + ((ms // 45 + i * 3) % 10)
    screen.pixel(22 + (i % 2), y, dim("#3caaff", k))
  end
end

return {
  input = function()
    if input.control == "watered" then
      state.watered, splash = now, true
    end
  end,
  frame = function(ctx)
    now = ctx.epochSec
    state.born = state.born or now
    state.watered = state.watered or now
    if state.watered > now then state.watered = now end
    if splash then pour, splash = ctx.monoMs + 3000, false end
    if pour and ctx.monoMs >= pour then pour = nil end
    local every = (EVERY[settings.every] or 7) * DAY
    local left = state.watered + every - now
    local f = (now - state.watered) / every
    state.mood = f < 0.8 and "happy" or f < 1 and "thirsty" or "wilting"
    if left <= 0 then
      state.next = "now"
    elseif left < DAY then
      state.next = "in " .. math.ceil(left / 3600) .. " h"
    else
      local d = math.ceil(left / DAY)
      state.next = "in " .. d .. (d == 1 and " day" or " days")
    end
    local stage = math.min(5, 1 + (now - state.born) // (7 * DAY))
    local k = ctx.night and 0.5 or 1
    pot(k)
    plant(stage, pour and "happy" or state.mood, ctx, k)
    if pour then watering(ctx.monoMs, k) end
    if left <= 0 then
      local on = (ctx.monoMs // 700) % 2 == 0
      screen.text("WATER ME", 40, 21, 11, dim(on and "#ffffff" or "#a1b5bd", k))
    else
      screen.text("WATER IN", 40, 12, 6, dim("#6f8793", k))
      local words = left < DAY and (math.ceil(left / 3600) .. " H") or
        (math.ceil(left / DAY) .. (math.ceil(left / DAY) == 1 and " DAY" or " DAYS"))
      screen.text(words, 40, 26, 11, dim(state.mood == "happy" and "#e6f5e9" or "#e8d9a0", k))
    end
  end
}
