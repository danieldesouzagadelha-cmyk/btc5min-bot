import time
from telegram_bot import send_message

# =====================
# CONFIGURAÇÃO
# =====================

capital = 50
btc = 0
position_price = None
last_price = None

# estatísticas
trades = 0
wins = 0
losses = 0

# cooldown
last_trade_time = 0
cooldown_seconds = 30

# estratégia
ENTRY_DROP = -15
TAKE_PROFIT = 25
STOP_LOSS = -20


def trade(price):

    global capital
    global btc
    global position_price
    global trades
    global wins
    global losses
    global last_trade_time
    global last_price

    now = time.time()

    # =====================
    # PRIMEIRO LOOP
    # =====================

    if last_price is None:
        last_price = price
        return

    change = price - last_price

    # =====================
    # COOLDOWN
    # =====================

    if now - last_trade_time < cooldown_seconds:
        print("Cooldown ativo")
        last_price = price
        return

    # =====================
    # BUY
    # =====================

    if btc == 0 and change <= ENTRY_DROP and capital >= 10:

        btc = 10 / price
        capital -= 10
        position_price = price

        last_trade_time = now

        print("BUY:", price)

        send_message(
            f"🟢 BUY BTC\n"
            f"Preço: {price}"
        )

        last_price = price
        return

    # =====================
    # SELL
    # =====================

    if btc > 0:

        move = price - position_price

        # TAKE PROFIT
        if move >= TAKE_PROFIT:

            capital += btc * price
            btc = 0

            trades += 1
            wins += 1

            last_trade_time = now

            send_message(
                f"🔴 TAKE PROFIT\n"
                f"Preço: {price}\n"
                f"Lucro: {round(move,2)}"
            )

        # STOP LOSS
        elif move <= STOP_LOSS:

            capital += btc * price
            btc = 0

            trades += 1
            losses += 1

            last_trade_time = now

            send_message(
                f"⚠️ STOP LOSS\n"
                f"Preço: {price}\n"
                f"Perda: {round(move,2)}"
            )

    # =====================
    # ESTATÍSTICAS
    # =====================

    total = capital + btc * price

    winrate = 0
    if trades > 0:
        winrate = (wins / trades) * 100

    print("Preço:", price)
    print("Capital:", round(total, 2))
    print("Trades:", trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("WinRate:", round(winrate, 2))

    last_price = price
