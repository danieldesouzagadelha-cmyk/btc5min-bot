import ccxt

exchange = ccxt.mexc({
    "enableRateLimit": True
})

symbol = "BTC/USDT"

def get_price():
    ticker = exchange.fetch_ticker(symbol)
    return ticker["last"]
