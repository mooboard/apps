-- steep timers for tea and the French press + the water darkens as it steeps, a tea bag dunks or the plunger waits,
-- and at the end it says it's ready (with a chime on a board with a speaker) + nothing leaves the board
local BREWS = {   -- name, seconds, the brew's color when it's done
  {"Green tea", 150, "#b5c84a"},
  {"Black tea", 240, "#8a3c12"},
  {"Oolong", 180, "#c27a2a"},
  {"Herbal tea", 300, "#c0392b"},
  {"French press", 240, "#4a2a14"},
}
local KEYS = {green = 1, black = 2, oolong = 3, herbal = 4, press = 5}   -- each brew's button
local WATER = {159, 199, 216}
local READY_FOR = 10 * 60
local now, rang = 0, false

local function hex(r, g, b, k)
  k = k or 1
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function rgb(h)
  return tonumber(h:sub(2, 3), 16), tonumber(h:sub(4, 5), 16), tonumber(h:sub(6, 7), 16)
end

local function blend(done_hex, u, k)
  local r, g, b = rgb(done_hex)
  return hex(WATER[1] + (r - WATER[1]) * u, WATER[2] + (g - WATER[2]) * u, WATER[3] + (b - WATER[3]) * u, k)
end

local function steam(ms, x, k)
  for i = 0, 1 do
    for j = 0, 3 do
      local y = 9 - j * 2 - (ms // 250 + i) % 2
      local dx = math.floor(math.sin(ms / 400 + j + i * 2) + 0.5)
      if y > 1 then screen.pixel(x + i * 5 + dx, y, hex(111, 135, 147, k)) end
    end
  end
end

local function mug(u, color, ms, k)
  local wall = hex(217, 217, 217, k)
  screen.rect(6, 12, 1, 18, wall, true)
  screen.rect(24, 12, 1, 18, wall, true)
  screen.rect(6, 29, 19, 1, wall, true)
  screen.rect(25, 15, 3, 1, wall, true)
  screen.rect(27, 15, 1, 9, wall, true)
  screen.rect(25, 23, 3, 1, wall, true)
  screen.rect(7, 14, 17, 15, blend(color, u, k), true)
  if u < 1 then
    -- the tea bag dunks every 2.5 s
    local dip = ((ms % 2500) < 600) and 2 or 0
    screen.line(17, 4, 17, 15 + dip, hex(200, 200, 200, k))
    screen.rect(16, 2, 3, 3, hex(255, 149, 0, k), true)
    screen.rect(15, 16 + dip, 4, 5, hex(216, 200, 160, k), true)
  end
end

local function press(u, color, ms, k, done_ms)
  local frame = hex(192, 192, 192, k)
  local glass = hex(120, 140, 150, k)
  screen.rect(7, 8, 1, 22, glass, true)
  screen.rect(23, 8, 1, 22, glass, true)
  screen.rect(6, 8, 19, 1, frame, true)
  screen.rect(6, 29, 19, 1, frame, true)
  screen.rect(24, 12, 3, 1, frame, true)
  screen.rect(26, 12, 1, 12, frame, true)
  screen.rect(24, 23, 3, 1, frame, true)
  screen.rect(8, 11, 15, 18, blend(color, u, k), true)
  -- the plunger waits at the top, then presses down over 1.5 s once it's ready
  local plate = 10
  if done_ms then plate = 10 + math.floor(math.min(1, done_ms / 1500) * 16) end
  screen.rect(8, plate, 15, 1, frame, true)
  screen.line(15, 3, 15, plate - 1, frame)
  screen.rect(13, 2, 5, 1, frame, true)
end

return {
  input = function()
    local pick = KEYS[input.control]
    if input.control == "green" or input.control == "black" or input.control == "oolong" or
      input.control == "herbal" or input.control == "press" then
      state.pick, state.ends, rang = pick, now + BREWS[pick][2], false
    elseif input.control == "stop" then
      state.ends = nil
    end
  end,
  frame = function(ctx)
    now = ctx.epochSec
    local k = ctx.night and 0.5 or 1
    local brew = BREWS[state.pick or 0]
    if state.ends and (not brew or now >= state.ends + READY_FOR) then state.ends = nil end
    if not state.ends or not brew then
      state.left, state.brew = "off", nil
      mug(0, "#8a3c12", 0, k * 0.6)
      screen.text("PICK A BREW", 34, 20, 9, hex(161, 181, 189, k))
      return
    end
    state.brew = brew[1]
    local left = state.ends - now
    local u = math.max(0, math.min(1, 1 - left / brew[2]))
    local done_ms = nil
    if left <= 0 then
      done_ms = (-left) * 1000 + ctx.monoMs % 1000
      state.left = "ready"
      if not rang then
        rang = true
        if sound then sound.play("done") end
      end
    else
      state.left = string.format("%d:%02d", left // 60, left % 60)
    end
    if brew[1] == "French press" then press(u, brew[3], ctx.monoMs, k, done_ms) else mug(u, brew[3], ctx.monoMs, k) end
    steam(ctx.monoMs, brew[1] == "French press" and 19 or 9, k)
    screen.text(string.upper(brew[1]), 34, 11, 6, hex(111, 135, 147, k))
    if left <= 0 then
      local on = (ctx.monoMs // 600) % 2 == 0
      screen.text("READY", 34, 26, 13, on and hex(255, 255, 255, k) or hex(161, 181, 189, k))
    else
      screen.text(state.left, 34, 26, 13, hex(255, 255, 255, k))
      local r, g, b = rgb(brew[3])
      screen.rect(34, 29, math.floor(88 * u), 1, hex(math.max(r, 90), math.max(g, 60), math.max(b, 30), k), true)
      screen.rect(34 + math.floor(88 * u), 29, 88 - math.floor(88 * u), 1, hex(42, 57, 68, k), true)
    end
  end
}
