-- breathe in, hold, breathe out, and hold, a few seconds each + a dot walks the square's sides, one side a phase, and
-- the square fills as you breathe in and empties as you breathe out + nothing leaves the board
local PATTERNS = {   -- each phase: its name, seconds, and the stretch of the square's sides it walks
  ["Box 4-4-4-4"] = {{"in", 4, 0, 1}, {"hold", 4, 1, 2}, {"out", 4, 2, 3}, {"rest", 4, 3, 4}},
  ["Relax 4-7-8"] = {{"in", 4, 0, 1}, {"hold", 7, 1, 2}, {"out", 8, 2, 4}},
  ["Even 5-5"] = {{"in", 5, 0, 2}, {"out", 5, 2, 4}},
}
local WORDS = {["in"] = "BREATHE IN", hold = "HOLD", out = "BREATHE OUT", rest = "HOLD"}
local X0, Y0, L = 5, 5, 21   -- the square's top left corner and its side, corner to corner
local t0, mono = nil, 0

local function rgb(hex)
  return tonumber(hex:sub(2, 3), 16) or 119, tonumber(hex:sub(4, 5), 16) or 237, tonumber(hex:sub(6, 7), 16) or 215
end

local function shade(r, g, b, k)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function at(p)
  -- a point p of the way round the square, 0 to 4: up the left, across the top, down the right, back on the bottom
  local side, u = math.floor(p) % 4, p - math.floor(p)
  local d = math.floor(u * L + 0.5)
  if side == 0 then return X0, Y0 + L - d end
  if side == 1 then return X0 + d, Y0 end
  if side == 2 then return X0 + L, Y0 + d end
  return X0 + L - d, Y0 + L
end

local function where(ms, phases)
  local total = 0
  for _, ph in ipairs(phases) do total = total + ph[2] end
  local t = (ms % (total * 1000)) / 1000
  for _, ph in ipairs(phases) do
    if t < ph[2] then return ph, t end
    t = t - ph[2]
  end
  return phases[1], 0
end

return {
  input = function()
    if input.control == "restart" then t0 = mono end
  end,
  frame = function(ctx)
    mono = ctx.monoMs
    if not t0 or mono < t0 then t0 = mono end
    local phases = PATTERNS[settings.pattern] or PATTERNS["Box 4-4-4-4"]
    local total = 0
    for _, ph in ipairs(phases) do total = total + ph[2] end
    local ms = mono - t0
    local ph, t = where(ms, phases)
    local u = t / ph[2]
    state.phase = ph[1]
    state.left = math.ceil(ph[2] - t - 0.0005)
    state.rounds = ms // (total * 1000)

    local k = ctx.night and 0.45 or 1
    local r, g, b = rgb(settings.color or "#77EDD7")
    local fill = ph[1] == "in" and u or ph[1] == "hold" and 1 or ph[1] == "out" and 1 - u or 0
    -- the square, dim, and the lungs filling it from the bottom
    screen.rect(X0, Y0, L + 1, L + 1, shade(r, g, b, 0.22 * k), false)
    local rows = math.floor(fill * (L - 3) + 0.5)
    if rows > 0 then
      screen.rect(X0 + 2, Y0 + L - 1 - rows, L - 3, rows, shade(r, g, b, (0.2 + 0.25 * fill) * k), true)
      screen.rect(X0 + 2, Y0 + L - 1 - rows, L - 3, 1, shade(r, g, b, 0.7 * k), true)
    end
    -- this phase's walk so far, bright, and the dot at its head
    local p0, p1 = ph[3], ph[3] + (ph[4] - ph[3]) * u
    local p = p0
    while p < p1 do
      local x, y = at(p)
      screen.pixel(x, y, shade(r, g, b, k))
      p = p + 1 / (L * 2)
    end
    local x, y = at(p1)
    screen.rect(x - 1, y - 1, 3, 3, shade(255, 255, 255, 0.9 * k), true)
    -- the words and the count
    screen.text(WORDS[ph[1]], 36, 13, 9, shade(r, g, b, k))
    screen.text(tostring(state.left), 36, 28, 13, shade(255, 255, 255, 0.85 * k))
  end
}
