-- Stocks and crypto: your watchlist with today's change, three stocks then two coins + stocks come through mooboard's
-- /quotes in the order asked and coins from CoinGecko by ticker, so nobody needs a key u906 c7619
local up, down, flat, dim = "#34d378", "#ff5252", "#96a0aa", "#a1b5bd"

local function price(value)
  if value >= 1000 then return string.format("%.0f", value) end
  if value >= 100 then return string.format("%.1f", value) end
  if value >= 1 then return string.format("%.2f", value) end
  return string.format("%.4f", value)
end

-- a triangle up or down, or a dash, five columns wide with its top left at x, y
local function arrow(x, y, change)
  if change >= 0.05 then
    for k = 0, 2 do screen.line(x + 2 - k, y + 1 + k, x + 2 + k, y + 1 + k, up) end
    return up
  elseif change <= -0.05 then
    for k = 0, 2 do screen.line(x + 2 - k, y + 3 - k, x + 2 + k, y + 3 - k, down) end
    return down
  end
  screen.line(x, y + 2, x + 4, y + 2, flat)
  return flat
end

local function row(y, name, value, change)
  screen.text(name, 2, y, 8, "#ffffff")
  screen.text(price(value), 38, y, 8, "#ffffff")
  local color = arrow(84, y - 5, change)
  screen.text(string.format("%.1f%%", math.abs(change)), 92, y, 8, color)
end

local function stocks()
  local rows = {}
  local feed = (data.stocks or {}).value
  local q = type(feed) == "table" and type(feed.q) == "table" and feed.q or {}
  for i = 1, 3 do
    local quote = q[i]
    if type(quote) == "table" and type(quote.s) == "string" and type(quote.c) == "number" and quote.c > 0 then
      rows[#rows + 1] = {quote.s, quote.c, type(quote.dp) == "number" and quote.dp or 0}
    end
  end
  return rows
end

local function coins()
  local rows = {}
  local feed = (data.coins or {}).value
  for i = 1, 2 do
    local ticker = settings["coin" .. i]
    local coin = type(feed) == "table" and type(ticker) == "string" and feed[string.lower(ticker)] or nil
    if type(coin) == "table" and type(coin.usd) == "number" then
      rows[#rows + 1] = {string.upper(ticker), coin.usd, type(coin.usd_24h_change) == "number" and coin.usd_24h_change or 0}
    end
  end
  return rows
end

return {
  frame = function(ctx)
    local pages = {}
    local s, c = stocks(), coins()
    if #s > 0 then pages[#pages + 1] = s end
    if #c > 0 then pages[#pages + 1] = c end
    if #pages == 0 then
      screen.text("Waiting for prices", 3, 20, 8, dim)
      return
    end
    local page = pages[(ctx.elapsedMs // 6000) % #pages + 1]
    for i, r in ipairs(page) do row(i * 10 + (#page == 2 and 4 or -1), r[1], r[2], r[3]) end
  end
}
