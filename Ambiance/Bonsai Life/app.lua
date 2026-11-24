-- a bonsai in its pot through the year + blossoms and petals in spring, deep green in summer, orange leaves falling in
-- fall, and snow on bare branches in winter + the season follows the date (flipped south of the equator) or the one you
-- pick, and the pads sway a little + nothing leaves the board
local SEASONS = {["Spring"] = "spring", ["Summer"] = "summer", ["Fall"] = "fall", ["Winter"] = "winter"}
local BY_MONTH = {"winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "fall", "fall", "fall",
                  "winter"}
local LOOK = {   -- each pad's top and its shade
  spring = {"#5fd36e", "#2f9e4a"},
  summer = {"#3cc85a", "#1f8a3c"},
  fall = {"#ff8c1e", "#e0502a"},
}
local PADS = {{48, 14, 8, 3}, {80, 10, 9, 3}, {67, 6, 7, 2}, {56, 9, 5, 2}}   -- center x, y, half width, half height
local BRANCHES = {{61, 18, 49, 15}, {65, 14, 79, 11}, {66, 13, 67, 7}, {62, 16, 56, 10}}
local TRUNK = {{64, 24}, {64, 23}, {63, 22}, {62, 21}, {61, 20}, {61, 19}, {61, 18}, {62, 17}, {63, 16}, {64, 15},
               {65, 14}, {66, 13}}

local function rgb(h)
  return tonumber(h:sub(2, 3), 16) or 0, tonumber(h:sub(4, 5), 16) or 0, tonumber(h:sub(6, 7), 16) or 0
end

local function dim(h, k)
  if k >= 1 then return h end
  local r, g, b = rgb(h)
  return string.format("#%02x%02x%02x", math.floor(r * k), math.floor(g * k), math.floor(b * k))
end

local function pad(cx, cy, rx, ry, top, shade)
  for dy = -ry, ry do
    local half = math.floor(rx * math.sqrt(1 - (dy / (ry + 0.5)) ^ 2) + 0.5)
    screen.rect(cx - half, cy + dy, half * 2 + 1, 1, dy <= 0 and top or shade, true)
  end
end

local function hash(n)
  return ((n * 1103515245 + 12345) % 2147483648) // 65536
end

local function fallers(ms, count, color, k, speed, drift)
  -- petals, leaves, or snow, each on its own loop down the screen, kept off the edges
  for i = 1, count do
    local period = 5000 + hash(i) % 4000
    local t = ((ms + hash(i * 7) % period) % period) / period
    local x = 30 + hash(i * 13) % 70 + math.floor(drift * t * 12 + math.sin(t * 6.28 + i) * 2)
    local y = 1 + math.floor(t * 28 * speed) % 29
    if x > 1 and x < 126 then screen.pixel(x, y, dim(color, k)) end
  end
end

return {
  frame = function(ctx)
    local season = SEASONS[settings.season]
    if settings.season == "By the date" or not season then
      local m = ctx.month or 1
      if ctx.lat and ctx.lat < 0 then m = (m + 5) % 12 + 1 end
      season = BY_MONTH[m]
    end
    state.season = season
    local k = ctx.night and 0.55 or 1
    local ms = ctx.monoMs
    -- the shelf, the pot, and its moss
    screen.rect(34, 30, 60, 1, dim("#5a3820", k), true)
    local pot = dim(settings.pot or "#3C6E8C", k)
    screen.rect(50, 25, 29, 1, pot, true)
    screen.rect(52, 26, 25, 3, pot, true)
    screen.rect(53, 29, 3, 1, pot, true)
    screen.rect(73, 29, 3, 1, pot, true)
    screen.rect(52, 24, 25, 1, dim("#3a5a2a", k), true)
    -- the trunk, two dots wide, and its branches
    local bark = dim("#7a5230", k)
    for _, p in ipairs(TRUNK) do screen.rect(p[1] - 1, p[2], 2, 1, bark, true) end
    for _, b in ipairs(BRANCHES) do screen.line(b[1], b[2], b[3], b[4], bark) end
    if season == "winter" then
      local snow = dim("#f0f6ff", k)
      for _, b in ipairs(BRANCHES) do
        screen.line(b[1], b[2] - 1, b[3], b[4] - 1, snow)
        screen.line(b[3], b[4], b[3] + (b[3] > 64 and 2 or -2), b[4] - 2, bark)
      end
      screen.rect(50, 24, 29, 1, snow, true)
      fallers(ms, 18, "#f0f6ff", k, 1, 0.5)
    else
      local look = LOOK[season]
      for i, p in ipairs(PADS) do
        local sway = math.floor(math.sin(ms / 1400 + i * 1.7) * 1.2 + 0.5)
        pad(p[1] + sway, p[2], p[3], p[4], dim(look[1], k), dim(look[2], k))
      end
      if season == "spring" then
        for i = 1, 16 do
          local p = PADS[(i - 1) % #PADS + 1]
          local sway = math.floor(math.sin(ms / 1400 + ((i - 1) % #PADS + 1) * 1.7) * 1.2 + 0.5)
          local x = p[1] + sway - p[3] + 1 + hash(i * 3) % (p[3] * 2 - 1)
          local y = p[2] - p[4] + 1 + hash(i * 5) % (p[4] * 2)
          screen.pixel(x, y, dim("#ff9ec4", k))
        end
        fallers(ms, 8, "#ff9ec4", k, 0.9, 1)
      elseif season == "fall" then
        fallers(ms, 12, "#ff8c1e", k, 0.8, 1.5)
      elseif ctx.night then
        for i = 1, 5 do
          local x = 36 + hash(i * 17) % 56 + math.floor(math.sin(ms / 900 + i) * 3)
          local y = 4 + hash(i * 19) % 16 + math.floor(math.cos(ms / 1100 + i) * 2)
          if (ms // 300 + i) % 5 ~= 0 then screen.pixel(x, y, "#c8e650") end
        end
      end
    end
    if ctx.night then
      screen.circle(110, 7, 3, dim("#f5e9d6", 0.6))
      screen.circle(112, 6, 3, "#000000")
    end
  end
}
