-- oscilloscope + waves and lissajous figures with afterglow
local TAU = 2 * math.pi
local TINTS = {Green = {90, 255, 120}, Amber = {255, 176, 40}, Blue = {80, 180, 255}, White = {215, 225, 255}}
local GLOW = {1.0, 0.72, 0.46, 0.28, 0.16, 0.09}
local RATIOS = {{1, 2}, {3, 2}, {3, 4}, {1, 3}, {2, 3}, {5, 4}}
local SWEEP, SHAPE, FIGURE, BOTH = 1600, 9000, 12000, 15000

local function tint(f)
  local t = TINTS[settings.phosphor] or TINTS.Green
  return math.floor(t[1] * f) * 65536 + math.floor(t[2] * f) * 256 + math.floor(t[3] * f)
end

-- the head is white hot
local function head()
  local t = TINTS[settings.phosphor] or TINTS.Green
  local function mix(c) return math.floor(c + (255 - c) * 0.6) end
  return mix(t[1]) * 65536 + mix(t[2]) * 256 + mix(t[3])
end

local function grid()
  local c, axis = tint(0.16), tint(0.24)
  for x = 16, 112, 16 do
    for y = 4, 28, 4 do screen.pixel(x, y, x == 64 and axis or c) end
  end
  for x = 4, 124, 4 do
    screen.pixel(x, 8, c)
    screen.pixel(x, 24, c)
  end
  for x = 2, 125, 2 do screen.pixel(x, 16, axis) end
  for y = 2, 29, 2 do screen.pixel(64, y, axis) end
end

-- one of five shapes at phase u
local function shape(k, u)
  local a = TAU * u
  if k == 0 then return math.sin(a) end
  if k == 1 then return math.asin(math.sin(a)) * 2 / math.pi end
  if k == 2 then return (math.sin(a) + math.sin(3 * a) / 3 + math.sin(5 * a) / 5) * 1.08 end
  if k == 3 then return (math.sin(a) - math.sin(2 * a) / 2 + math.sin(3 * a) / 3) * 0.58 end
  return math.sin(3 * a) * (0.55 + 0.45 * math.sin(a / 2))
end

local function waves(ms)
  local slot = ms // SHAPE
  local k, nk = slot % 5, (slot + 1) % 5
  local blend = (ms % SHAPE) / SHAPE
  blend = blend < 0.82 and 0 or (blend - 0.82) / 0.18
  local beam = 2 + (ms % SWEEP) * 123 // SWEEP
  local drift = ms / 7000
  local levels, hot = {}, head()
  for i = 1, #GLOW do levels[i] = tint(GLOW[i]) end
  local ys = {}
  for x = 2, 125 do
    local u = (x - 2) / 124 * 2.5 + drift
    local w = shape(k, u)
    if blend > 0 then w = w + (shape(nk, u) - w) * blend end
    ys[x] = 16 - math.floor(w * 10 + 0.5)
  end
  for age = 123, 0, -1 do
    local x = 2 + (beam - 2 - age) % 124
    local c = age < 2 and hot or levels[age < 14 and 1 or age < 34 and 2 or age < 58 and 3 or age < 86 and 4 or age < 108 and 5 or 6]
    if x > 2 then screen.line(x - 1, ys[x - 1], x, ys[x], c) else screen.pixel(x, ys[x], c) end
  end
end

local function figures(ms)
  local r = RATIOS[(ms // FIGURE) % #RATIOS + 1]
  local into = ms % FIGURE
  local shown = into < 700 and into / 700 or 1
  local delta = ms / 3000
  local beam = (ms % 1500) / 1500
  local levels, hot = {}, head()
  for i = 1, #GLOW do levels[i] = tint(GLOW[i]) end
  local n = 96
  local px, py
  for k = 0, n do
    local f = k / n
    if f > shown then break end
    local s = TAU * f
    local x = 64 + math.floor(58 * math.sin(r[1] * s + delta) + 0.5)
    local y = 16 + math.floor(12 * math.sin(r[2] * s) + 0.5)
    local age = (beam - f) % 1
    local c = age < 0.02 and hot or levels[age < 0.1 and 1 or age < 0.22 and 2 or age < 0.4 and 3 or age < 0.6 and 4 or 5]
    if px then screen.line(px, py, x, y, c) end
    px, py = x, y
  end
end

return {
  frame = function(ctx)
    if settings.grid then grid() end
    local ms = ctx.elapsedMs or ctx.monoMs
    local mode = settings.trace
    if mode == "Both" then mode = (ms // BOTH) % 2 == 0 and "Waves" or "Figures" end
    if mode == "Figures" then figures(ms) else waves(ms) end
  end
}
