last_price = None

def detect_reversion(price, bids):

    global last_price

    if last_price is None:
        last_price = price
        return False

    price_drop = last_price - price

    last_price = price

    # detectar queda menor
    if price_drop < 5:
        return False

    # verificar liquidez no bid
    for bid in bids[:5]:

        bid_volume = bid[1]

        if bid_volume > 0.5:
            return True

    return False
