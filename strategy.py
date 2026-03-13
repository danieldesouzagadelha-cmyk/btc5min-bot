last_price = None

def detect_reversion(price, bids):

    global last_price

    if last_price is None:
        last_price = price
        return False

    price_drop = last_price - price

    last_price = price

    # queda mínima para considerar reversão
    if price_drop < 15:
        return False

    # verificar liquidez forte no bid
    for bid in bids[:5]:

        bid_price = bid[0]
        bid_volume = bid[1]

        if bid_volume > 1:   # parede grande
            return True

    return False
