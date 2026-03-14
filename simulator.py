import time
from telegram_bot import send_message

# =========================
# CAPITAL
# =========================

capital = 50
btc = 0
position_price = None

# =========================
# CONTROLE
# =========================

last_price = None
last_trade_time = 0
cooldown_seconds = 15

# =========================
# ESTATÍSTICAS
# =========================

trades = 0
wins = 0
losses = 0

# =========================
# PARÂMETROS
# =========================

ENTRY_DROP = 8
ENTRY_RISE = 8
TAKE_PROFIT = 15
STOP_LOSS = -12
IMBALANCE_TRIGGER = 2


def trade(price, bid, ask, bid_volume, ask_volume):

    global capital
    global btc
    global position_price
    global last_price
    global last_trade_time
    global trades
    global wins
    global losses

    now = time.time()

    if last_price is None:
        last_price = price
        return

    # =========================
    # MOVIMENTO DE PREÇO
    # =========================

    price_drop = last_price - price
    price_move = price - last_price

    # =========================
    # IMBALANCE
    # =========================

    imbalance = 0
    if ask_volume > 0:
        imbalance = bid_volume / ask_volume

    # evitar imbalance absurdo
    imbalance = min(imbalance, 50)

    print("Preço:", price)
    print("Bid:", bid)
    print("Ask:", ask)
    print("Price drop:", round(price_drop,2))
    print("Price move:", round(price_move,2))
    print("Bid volume:", bid_volume)
    print("Ask volume:", ask_volume)
    print("Imbalance:", round(imbalance,2))

    # =========================
    # PRESSÃO DE COMPRA
    # =========================

    buy_pressure = imbalance > IMBALANCE_TRIGGER

    if buy_pressure:
        print("BUY PRESSURE DETECTED")

    # =========================
    # REVERSÃO (queda)
    # =========================

    reversal = price_drop >= ENTRY_DROP and buy_pressure

    if reversal:
        print("REVERSÃO DETECTADA")

    # =========================
    # MOMENTUM (subida)
    # =========================

    momentum = price_move >= ENTRY_RISE and buy_pressure

    if momentum:
        print("MOMENTUM DETECTADO")

    # =========================
    # COOLDOWN
    # =========================

    if now - last_trade_time < cooldown_seconds:
        last_price = price
        return

    # =========================
    # BUY
    # =========================

    if btc == 0 and capital >= 10 and (reversal or momentum):

        btc = 10 / price
        capital -= 10
        position_price = price

        last_trade_time = now

        print("BUY EXECUTADO")

        send_message(
            f"🟢 BUY BTC\n"
            f"Preço: {price}"
        )

    # =========================
    # SELL
    # =========================

    if btc > 0:

        move = price - position_price

        if move >= TAKE_PROFIT:

            capital += btc * price
            btc = 0

            trades += 1
            wins += 1

            last_trade_time = now

            print("TAKE PROFIT")

            send_message(
                f"🔴 TAKE PROFIT\n"
                f"Preço: {price}\n"
                f"Lucro: {round(move,2)}"
            )

        elif move <= STOP_LOSS:

            capital += btc * price
            btc = 0

            trades += 1
            losses += 1

            last_trade_time = now

            print("STOP LOSS")

            send_message(
                f"⚠️ STOP LOSS\n"
                f"Preço: {price}\n"
                f"Perda: {round(move,2)}"
            )

    # =========================
    # ESTATÍSTICAS
    # =========================

    total = capital + btc * price

    winrate = 0
    if trades > 0:
        winrate = (wins / trades) * 100

    print("Capital:", round(total,2))
    print("Trades:", trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("WinRate:", round(winrate,2))

    last_price = price
