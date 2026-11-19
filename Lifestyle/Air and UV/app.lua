-- US air quality index and UV index from Open-Meteo, no key
local AQI = {
  {50, "#34c759", "GOOD"}, {100, "#ffd60a", "FAIR"}, {150, "#ff9500", "SENSITIVE"},
  {200, "#ff3b30", "BAD"}, {300, "#af52de", "VERY BAD"}, {9999, "#c2185b", "HAZARD"},
}
local UV = {
  {2.99, "#34c759", "LOW"}, {5.99, "#ffd60a", "MODERATE"}, {7.99, "#ff9500", "HIGH"},
  {10.99, "#ff3b30", "VERY HIGH"}, {99, "#af52de", "EXTREME"},
}

local function level(table_, value)
  for i = 1, #table_ do
    if value <= table_[i][1] then return i, table_[i] end
  end
  return #table_, table_[#table_]
end

local function gauge(x, y, width, steps, at, color, tick)
  -- steps dim segments with the current one lit
  local seg = width // steps
  for i = 1, steps do
    local c = (i <= at) and color or "#2a3338"
    screen.rect(x + (i - 1) * seg, y, seg - 1, 2, c, true)
  end
  if tick then screen.rect(x + (at - 1) * seg, y + 3, seg - 1, 1, color, true) end
end

local function panel(x0, label, number, word, color, steps, at, ctx)
  screen.text(label, x0, 8, 6, "#6f8793")
  screen.text(number, x0, 22, 13, color)
  screen.text(word, x0, 30, 6, color)
  local pulse = math.floor(ctx.monoMs / 600) % 2 == 0
  gauge(x0 + 30, 5, 30, steps, at, color, pulse)
end

return {
  frame = function(ctx)
    local feed = data.air or {}
    local value = feed.value
    local current = value and value.current
    if not current or current.us_aqi == nil then
      local dots = math.floor(ctx.monoMs / 400) % 4
      screen.text("AIR AND UV", 30, 17, 9, "#a1b5bd")
      screen.text(string.sub("...", 1, dots), 100, 17, 9, "#a1b5bd")
      return
    end
    local aqi = math.floor(tonumber(current.us_aqi) + 0.5)
    local uv = tonumber(current.uv_index) or 0
    local ai, arow = level(AQI, aqi)
    local ui, urow = level(UV, uv)
    state.aqi = aqi .. " " .. arow[3]
    state.uv = (math.floor(uv * 10 + 0.5) / 10) .. " " .. urow[3]
    panel(2, "AIR", tostring(aqi), arow[3], arow[2], 6, ai, ctx)
    screen.rect(64, 3, 1, 26, "#1d2a33", true)
    panel(67, "UV", tostring(math.floor(uv + 0.5)), urow[3], urow[2], 5, ui, ctx)
    if feed.status ~= "ok" and feed.status ~= nil then screen.pixel(126, 2, "#ff9500") end
  end
}
