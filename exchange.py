import ccxt

exchange = ccxt.mexc({
    "enableRateLimit": True
})

symbol = "BTC/USDT"

def get_market():

    ticker = exchange.fetch_ticker(symbol)
    orderbook = exchange.fetch_order_book(symbol)

    price = ticker["last"]

    bids = orderbook["bids"]
    asks = orderbook["asks"]

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    return price, bids, asks, best_bid, best_ask
