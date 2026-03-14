last_price = None

def detect_reversion(price, bids, asks):

    global last_price

    # inicializar primeiro preço
    if last_price is None:
        last_price = price
        return False

    # calcular movimento de preço
    price_drop = last_price - price

    last_price = price

    print("Price drop:", round(price_drop,2))

    # filtro mínimo de movimento
    if price_drop < 5:
        return False

    # calcular volume no bid
    bid_volume = sum(b[1] for b in bids[:10])

    # calcular volume no ask
    ask_volume = sum(a[1] for a in asks[:10])

    if ask_volume == 0:
        return False

    imbalance = bid_volume / ask_volume

    print("Bid volume:", round(bid_volume,2))
    print("Ask volume:", round(ask_volume,2))
    print("Imbalance:", round(imbalance,2))

    # compradores dominando
    if imbalance > 1.3:
        print("BUY PRESSURE DETECTED")
        return True

    return False
