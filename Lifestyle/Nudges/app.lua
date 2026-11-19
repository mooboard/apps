local WATER = {["30 min"] = 30, ["45 min"] = 45, ["1 hour"] = 60, ["90 min"] = 90, ["2 hours"] = 120}
local STAND = {["20 min"] = 20, ["30 min"] = 30, ["45 min"] = 45, ["1 hour"] = 60, ["90 min"] = 90}
local QUIET = {["9 pm to 7 am"] = {21, 7}, ["10 pm to 7 am"] = {22, 7}, ["11 pm to 8 am"] = {23, 8}}
local BLUE, SKIN, DIM = "#3caaff", "#f5e9d6", "#2a3944"
local now = 0

local function quiet(ctx)
  if settings.quiet == "Night mode" then return ctx.night end
  local q = QUIET[settings.quiet]
  if not q then return false end
  local h = ctx.hour
  if q[1] > q[2] then return h >= q[1] or h < q[2] end
  return h >= q[1] and h < q[2]
end

local function left(last, mins)
  return mins * 60 - (now - last)
end

local function words(sec)
  local m = math.ceil(sec / 60)
  if m >= 60 then return math.floor(m / 60) .. "h " .. (m % 60) .. "m" end
  return m .. " min"
end

local function glass(x, y, fill, color, edge)
  -- 12 wide, 16 tall tapered glass, fill 0 to 1
  for row = 0, 15 do
    local w = 12 - math.floor(row / 5)
    local x0 = x + math.floor((12 - w) / 2)
    screen.pixel(x0, y + row, edge)
    screen.pixel(x0 + w - 1, y + row, edge)
  end
  screen.rect(x + 2, y + 15, 8, 1, edge, true)
  local h = math.floor(fill * 14 + 0.5)
  for row = 0, h - 1 do
    local yy = y + 14 - row
    local w = 12 - math.floor((yy - y) / 5)
    local x0 = x + math.floor((12 - w) / 2)
    screen.rect(x0 + 1, yy, w - 2, 1, color, true)
  end
end

local function person(x, y, standing, bob, color, edge)
  y = y + bob
  screen.circle(x + 6, y + 2, 2, edge == DIM and DIM or SKIN)
  if standing then
    screen.rect(x + 5, y + 5, 3, 6, color, true)
    screen.rect(x + 5, y + 11, 1, 6, color, true)
    screen.rect(x + 7, y + 11, 1, 6, color, true)
    screen.line(x + 3, y + 8, x + 5, y + 6, color)
    screen.line(x + 10, y + 8, x + 8, y + 6, color)
  else
    screen.rect(x + 5, y + 5, 3, 5, color, true)
    screen.rect(x + 5, y + 10, 6, 1, color, true)
    screen.rect(x + 10, y + 10, 1, 5, color, true)
    screen.rect(x + 2, y + 12, 3, 1, edge, true)   -- the chair
    screen.rect(x + 2, y + 12, 1, 5, edge, true)
    screen.line(x + 8, y + 7, x + 12, y + 8, color)
  end
end

local function half(x0, kind, ctx, q)
  local due, text, sub
  if kind == "water" then
    local mins = WATER[settings.water] or 60
    local r = left(state.water_at, mins)
    due = r <= 0
    local fill = math.max(0, math.min(1, r / (mins * 60)))
    local pulse = due and (math.floor(ctx.monoMs / 500) % 2 == 0)
    glass(x0 + 3, 8, q and 0.4 or (due and 0 or fill), q and DIM or (pulse and "#9fd8ff" or BLUE), q and DIM or "#6f8793")
    if due and not q then
      local drop = (ctx.monoMs // 120) % 12
      screen.pixel(x0 + 9, 2 + drop // 2, BLUE)
    end
    text = q and "QUIET" or (due and "DRINK" or words(r))
    sub = "WATER"
    state.water_left = q and "quiet" or (due and "now" or words(r))
  else
    local mins = STAND[settings.stand] or 45
    local r = left(state.stand_at, mins)
    due = r <= 0
    local bob = (due and not q and math.floor(ctx.monoMs / 400) % 2) or 0
    person(x0 + 3, 7, state.standing, bob, q and DIM or "#ffb81c", q and DIM or "#6f8793")
    text = q and "QUIET" or (due and (state.standing and "SIT" or "STAND") or words(r))
    sub = state.standing and "UP" or "SEATED"
    state.stand_left = q and "quiet" or (due and "now" or words(r))
  end
  local c = q and DIM or (due and "#ffffff" or "#a1b5bd")
  screen.text(sub, x0 + 17, 11, 6, q and DIM or "#6f8793")
  screen.text(text, x0 + 17, 25, 8, c)
end

return {
  start = function()
    state.standing = state.standing or false
  end,
  input = function()
    if input.control == "drank" then state.water_at = now
    elseif input.control == "moved" then
      state.stand_at = now
      state.standing = not state.standing
    end
  end,
  frame = function(ctx)
    now = ctx.epochSec
    state.water_at = state.water_at or now
    state.stand_at = state.stand_at or now
    if state.water_at > now then state.water_at = now end
    if state.stand_at > now then state.stand_at = now end
    local q = quiet(ctx)
    if settings.show == "Both" then
      half(1, "water", ctx, q)
      half(65, "stand", ctx, q)
      screen.rect(64, 4, 1, 24, "#1d2a33", true)
    elseif settings.show == "Water" then
      half(34, "water", ctx, q)
    else
      half(34, "stand", ctx, q)
    end
  end
}
