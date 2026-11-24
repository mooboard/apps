-- a small pixel pet that wanders the board, blinks, and naps at night + it gets hungry after 6 hours, eats when you
-- feed it, and hearts float up when you pet it + nothing leaves the board
local HUNGRY, STARVING = 6 * 3600, 12 * 3600
local BOWL = 110            -- the bowl's left edge
local FLOOR = 29            -- the row its feet stand on
local now, mono = 0, 0
local fed_ask, pet_ask, eat_until, love_until = false, false, nil, nil

local function rgb(hex)
  return tonumber(hex:sub(2, 3), 16) or 255, tonumber(hex:sub(4, 5), 16) or 183, tonumber(hex:sub(6, 7), 16) or 201
end

local function shade(hex, k)
  if k >= 1 then return hex end
  local r, g, b = rgb(hex)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function spot(w)
  -- where the pet heads in window w, 6 to 90
  local h = (w * 1103515245 + 12345) % 2147483648
  return 6 + (h // 65536) % 85
end

local function walk(ms, slow)
  -- 4 s windows: walk to the next spot, then stand + slow (hungry) windows are 6 s
  local span = slow and 6000 or 4000
  local w = ms // span
  local a, b = spot(w - 1), spot(w)
  local pace = slow and 0.02 or 0.04   -- dots a millisecond
  local t = ms % span
  local need = math.abs(b - a) / pace
  if t >= need then return b, b >= a and 1 or -1, false end
  local x = a + (b - a) * t / need
  return math.floor(x + 0.5), b >= a and 1 or -1, true
end

local function dot(x, y, c)
  screen.rect(x, y, 2, 2, c, true)
end

local function body(x, y, dir, color, step, k, blink, mouth)
  -- 9 x 7 dots drawn two to a dot, ears above and feet below
  local foot = shade(color, 0.6 * k)
  color = shade(color, k)
  screen.rect(x + 2, y, 14, 2, color, true)
  screen.rect(x, y + 2, 18, 10, color, true)
  screen.rect(x + 2, y + 12, 14, 2, color, true)
  dot(x + 2, y - 2, color)
  dot(x + 14, y - 2, color)
  if not blink then
    local e = dir > 0 and x + 10 or x + 2
    dot(e, y + 4, "#000000")
    dot(e + 4, y + 4, "#000000")
  end
  if mouth then dot(dir > 0 and x + 16 or x, y + 8, "#000000") end
  if step == 0 then
    dot(x + 4, y + 14, foot)
    dot(x + 12, y + 14, foot)
  else
    dot(x + 6, y + 14, foot)
    dot(x + 10, y + 14, foot)
  end
end

local function heart(x, y, color)
  -- 5 wide and 4 tall
  screen.rect(x, y, 2, 1, color, true)
  screen.rect(x + 3, y, 2, 1, color, true)
  screen.rect(x, y + 1, 5, 1, color, true)
  screen.rect(x + 1, y + 2, 3, 1, color, true)
  screen.pixel(x + 2, y + 3, color)
end

local function bowl(k, food)
  screen.rect(BOWL, 26, 12, 2, shade("#3caaff", k), true)
  screen.rect(BOWL + 1, 28, 10, 1, shade("#3caaff", k), true)
  for i = 1, food do screen.rect(BOWL + i + (i - 1), 25, 1, 1, shade("#c87832", k), true) end
end

return {
  input = function()
    if input.control == "feed" then
      state.fed, fed_ask = now, true
    elseif input.control == "pet" then
      pet_ask = true
    end
  end,
  frame = function(ctx)
    now, mono = ctx.epochSec, ctx.monoMs
    state.fed = state.fed or now
    if state.fed > now then state.fed = now end
    if fed_ask then eat_until, fed_ask = mono + 4000, false end
    if pet_ask then love_until, pet_ask = mono + 3000, false end
    if eat_until and mono >= eat_until then eat_until = nil end
    if love_until and mono >= love_until then love_until = nil end
    local hungry = now - state.fed
    local asleep = settings.sleep ~= false and ctx.night
    state.mood = asleep and "sleeping" or hungry >= STARVING and "very hungry" or hungry >= HUNGRY and "hungry" or
      "happy"
    local k = ctx.night and 0.5 or 1
    local color = settings.color or "#FFB7C9"
    screen.rect(2, FLOOR + 1, 124, 1, shade("#1d2a33", k), true)
    bowl(k, eat_until and math.min(6, math.ceil((eat_until - mono) / 700)) or 0)
    if asleep then
      local x, y = 52, FLOOR - 9
      local c = shade(color, k)
      screen.rect(x + 2, y, 18, 2, c, true)
      screen.rect(x, y + 2, 22, 8, c, true)
      dot(x + 4, y - 2, c)
      screen.rect(x + 12, y + 4, 4, 1, shade(color, 0.55 * k), true)
      for i = 0, 2 do
        local t = (mono + i * 1000) % 3000
        local zy = y - 2 - t // 300
        if zy > 2 then screen.text("z", x + 24 + i * 4 + t // 1000, zy, 6, shade("#8aa0ad", k)) end
      end
      return
    end
    local x, dir, moving
    if eat_until then
      x, dir, moving = BOWL - 19, 1, false
    else
      x, dir, moving = walk(mono, hungry >= HUNGRY)
    end
    local y = FLOOR - 15 - ((moving and (mono // 150) % 2 == 0) and 2 or 0)
    local blink = (mono % 3200) < 150
    local chew = eat_until and (mono // 200) % 2 == 0
    body(x, y, dir, color, moving and (mono // 150) % 2 or 0, k, blink, chew)
    if love_until then
      local t = 3000 - (love_until - mono)
      for i = 0, 1 do
        local hy = y - 4 - (t + i * 700) // 250 % 10
        if hy > 1 then heart(x + 2 + i * 9, hy, shade("#ff3b5c", k)) end
      end
    elseif state.mood ~= "happy" and (state.mood == "hungry" or (mono // 500) % 2 == 0) then
      -- a bubble with a bowl in it
      local bx, by = x + 19, y - 10
      screen.rect(bx, by, 11, 7, shade("#f5f5f5", k), false)
      screen.rect(bx + 2, by + 3, 7, 2, shade("#3caaff", k), true)
      screen.pixel(bx, by + 7, shade("#f5f5f5", k))
    end
  end
}
