-- vintage cassette deck + reels, meters, and auto reverse
local X0, Y0 = 3, 2
local HUB, FULL = 4, 10
local SPEED = 10   -- tape in dots a second
local SHELLS = {Smoke = {"#1c1c22", "#5a5a66"}, Cream = {"#3a342a", "#a89a7a"},
                Red = {"#3a1010", "#b03030"}, Blue = {"#10203a", "#3060b0"}}
local SEGS = 10

-- size 6 advances, most capitals 7 and digits 6
local W6 = {E = 6, F = 6, L = 6, P = 6, S = 6, T = 6, Y = 6, Z = 6, I = 3, J = 4, M = 8, O = 8, Q = 8, W = 10,
            [" "] = 3, [":"] = 3, ["."] = 3, ["-"] = 5, ["/"] = 4, ["+"] = 6}
for d = 0, 9 do W6[tostring(d)] = 6 end

local function width6(s)
  local n = 0
  for i = 1, #s do n = n + (W6[string.sub(s, i, i)] or 7) end
  return n - 1
end

-- side, progress, and seconds into the side
local function where(ctx)
  local side = settings.tape == "C90" and 2700 or 1800
  local pos = ctx.epochSec % (2 * side)
  if pos < side then return "A", pos / side, pos end
  return "B", 1 - (pos - side) / side, pos - side
end

local function packs(p)
  local area = FULL * FULL - HUB * HUB
  return math.sqrt(HUB * HUB + area * (1 - p)), math.sqrt(HUB * HUB + area * p)
end

local spin = {left = 0, right = 0, last = nil}

local function turn(ctx, r1, r2, side)
  local ms = ctx.monoMs
  local dt = spin.last and (ms - spin.last) or 0
  if dt < 0 or dt > 250 then dt = 0 end
  spin.last = ms
  local dir = side == "A" and 1 or -1
  spin.left = (spin.left + dir * SPEED / r1 * dt / 1000) % (2 * math.pi)
  spin.right = (spin.right + dir * SPEED / r2 * dt / 1000) % (2 * math.pi)
end

local function hub(cx, cy, angle)
  screen.circle(cx, cy, 3, "#b8b8c0")
  for k = 0, 5 do
    local a = angle + k * math.pi / 3
    screen.pixel(cx + math.floor(3 * math.cos(a) + 0.5), cy + math.floor(3 * math.sin(a) + 0.5), "#202024")
  end
  screen.pixel(cx, cy, "#000000")
end

local function cassette(ctx, side, p)
  local look = SHELLS[settings.shell] or SHELLS.Smoke
  local fill, edge = look[1], look[2]
  local w, h = 62, 28
  screen.rect(X0 + 1, Y0, w - 2, h, fill, true)
  screen.rect(X0, Y0 + 1, w, h - 2, fill, true)
  local r1, r2 = packs(p)
  local cy = Y0 + 16
  screen.circle(X0 + 15, cy, math.floor(r1 + 0.5), "#4a2a14")
  screen.circle(X0 + 46, cy, math.floor(r2 + 0.5), "#4a2a14")
  screen.rect(X0 + 20, Y0 + 13, 22, 7, "#3a3a40", false)
  hub(X0 + 15, cy, spin.left)
  hub(X0 + 46, cy, spin.right)
  -- the label and its stripe
  screen.rect(X0 + 4, Y0 + 2, 54, 8, "#8a8068", true)
  screen.rect(X0 + 4, Y0 + 10, 54, 1, "#c8501e", true)
  screen.rect(X0 + 5, Y0 + 3, 8, 6, "#1a1410", true)
  screen.text(side, X0 + 6, Y0 + 9, 6, "#8a8068")
  local words = string.upper(tostring(settings.label or ""))
  while width6(words) > 42 do
    local cut = nil
    for i = #words, 2, -1 do
      if string.sub(words, i, i) == " " then cut = i break end
    end
    if not cut then break end
    words = string.sub(words, 1, cut - 1)
  end
  while #words > 0 and width6(words) > 42 do words = string.sub(words, 1, #words - 1) end
  screen.text(words, X0 + 15, Y0 + 9, 6, "#1a1410")
  -- the head opening and tape
  for i = 0, 5 do
    screen.rect(X0 + 16 - i, Y0 + 21 + i, 30 + 2 * i, 1, "#26262c", true)
  end
  screen.pixel(X0 + 21, Y0 + 24, "#000000")
  screen.pixel(X0 + 40, Y0 + 24, "#000000")
  screen.rect(X0 + 24, Y0 + 26, 14, 1, "#4a2a14", true)
  -- the edge and screws on top
  screen.line(X0 + 1, Y0, X0 + w - 2, Y0, edge)
  screen.line(X0 + 1, Y0 + h - 1, X0 + w - 2, Y0 + h - 1, edge)
  screen.line(X0, Y0 + 1, X0, Y0 + h - 2, edge)
  screen.line(X0 + w - 1, Y0 + 1, X0 + w - 1, Y0 + h - 2, edge)
  screen.pixel(X0 + 2, Y0 + h - 3, edge)
  screen.pixel(X0 + w - 3, Y0 + h - 3, edge)
end

local function noise(i)
  return ((i * 1103515245 + 12345) // 65536) % 1000 / 1000
end

-- a music level from 0 to 1 at a tenth of a second
local function level(step, ch)
  local beat = math.exp(-((step * 100) % 500) / 180)
  return 0.3 + 0.42 * beat + 0.28 * noise(step * 2 + ch)
end

local function meter(y, label, ch, step)
  screen.text(label, 69, y + 5, 6, "#6f8793")
  local now, peak = level(step, ch), 0
  for j = 0, 9 do
    local v = level(step - j, ch)
    if v > peak then peak = v end
  end
  local lit, top = math.floor(now * SEGS + 0.5), math.floor(peak * SEGS + 0.5)
  for s = 1, SEGS do
    local on = s <= lit or s == top
    local c
    if s <= 7 then c = on and "#34c759" or "#0e2a14"
    elseif s <= 9 then c = on and "#ffb81c" or "#2a2008"
    else c = on and "#ff3b30" or "#2a0a08" end
    screen.rect(77 + (s - 1) * 5, y, 4, 4, c, true)
  end
end

local function deck(ctx, side, secs)
  for k = 0, 2 do screen.line(69 + k, 4 + k, 69 + k, 8 - k, "#34c759") end
  screen.text("PLAY", 75, 9, 6, "#a1b5bd")
  local n = secs // 3 % 1000
  local counter = (n < 10 and "00" or n < 100 and "0" or "") .. n
  if settings.meters then
    screen.text(counter, 107, 9, 6, "#ffb81c")
    local step = ctx.monoMs // 100
    meter(12, "L", 0, step)
    meter(19, "R", 1, step)
    screen.text("SIDE " .. side, 69, 30, 6, "#6f8793")
    local t = settings.tape == "C90" and "C90" or "C60"
    screen.text(t, 125 - width6(t), 30, 6, "#6f8793")
  else
    screen.text(counter, 81, 25, 13, "#ffb81c")
  end
end

return {
  frame = function(ctx)
    local side, p, secs = where(ctx)
    local r1, r2 = packs(p)
    turn(ctx, r1, r2, side)
    cassette(ctx, side, p)
    deck(ctx, side, secs)
  end
}
