-- the feed is {"user": name, "total": n, "levels": "0120..."} with one digit 0 to 4 a day, a week of 7 a column, Sunday first
local THEMES = {
  Green = {"#1c2a24", "#0e6b3a", "#26a641", "#39d353", "#7dffa0"},
  Teal = {"#1a2a2c", "#0f6a66", "#1fa89c", "#4fdcc8", "#b4fff2"},
  Amber = {"#2a2418", "#7a4a0a", "#c27a12", "#ffb81c", "#ffe08a"},
  Pink = {"#2a1c24", "#7a1e4e", "#c22e7a", "#ff4fa0", "#ffc0dc"},
  White = {"#222428", "#4a4f57", "#868c96", "#c8ced8", "#ffffff"},
}
local PITCH_X, PITCH_Y, X0, Y0 = 2, 3, 2, 10

local function digits(n)
  local s = tostring(n)
  local out, len = "", #s
  for i = 1, len do
    out = out .. string.sub(s, i, i)
    if (len - i) % 3 == 0 and i < len then out = out .. "," end
  end
  return out
end

return {
  frame = function(ctx)
    local palette = THEMES[settings.colors] or THEMES.Green
    local feed = data.grid or {}
    local value = feed.value
    local name = string.sub(tostring(settings.user), 1, 14)
    screen.text(name, 2, 7, 6, "#a1b5bd")
    if not value or type(value.levels) ~= "string" then
      -- a sweep of squares while it loads
      local sweep = math.floor(ctx.monoMs / 60) % 70
      for col = 0, 52 do
        for row = 0, 6 do
          local d = math.abs(col - sweep)
          screen.rect(X0 + col * PITCH_X, Y0 + row * PITCH_Y, 1, 2, d < 3 and palette[3] or palette[1], true)
        end
      end
      if value and value.error then screen.text("NO USER", 70, 7, 6, "#ff9500") end
      return
    end
    local levels = value.levels
    local count = #levels
    for i = 0, count - 1 do
      local col, row = i // 7, i % 7
      local lv = (string.byte(levels, i + 1) or 48) - 48
      if lv < 0 or lv > 4 then lv = 0 end
      local color = palette[lv + 1]
      if i == count - 1 or (i == count - 2 and false) then
        if math.floor(ctx.monoMs / 500) % 2 == 0 then color = "#ffffff" end
      end
      screen.rect(X0 + col * PITCH_X, Y0 + row * PITCH_Y, 1, 2, color, true)
    end
    state.count = tonumber(value.total) or 0
    if settings.total then
      local label = digits(state.count)
      screen.text(label, 126 - (#label * 6 - (#label - 1) // 4 * 3), 7, 6, "#ffffff")
    end
    if feed.status ~= "ok" and feed.status ~= nil then screen.pixel(126, 2, "#ff9500") end
  end
}
