import time
from telegram_bot import send_message

# capital inicial
capital = 50

# posição atual
btc = 0
position_price = None

# estatísticas
trades = 0
wins = 0
losses = 0

# cooldown
last_trade_time = 0
cooldown_seconds = 60


def trade(price):

    global capital
    global btc
    global position_price
    global trades
    global wins
    global losses
    global last_trade_time

    now = time.time()

    # =====================
    # COOLDOWN
    # =====================

    if now - last_trade_time < cooldown_seconds:
        print("Cooldown ativo")
        return

    # =====================
    # BUY
    # =====================

    if btc == 0 and capital >= 10:

        btc = 10 / price
        capital -= 10
        position_price = price

        last_trade_time = now

        print("BUY:", price)

        send_message(f"🟢 BUY BTC\nPreço: {price}")

        return

    # =====================
    # SELL
    # =====================

    if btc > 0:

        profit = price - position_price

        # TAKE PROFIT
        if profit >= 8:

            capital += btc * price
            btc = 0

            trades += 1
            wins += 1

            last_trade_time = now

            send_message(
                f"🔴 SELL (TP)\nPreço: {price}\nLucro: {round(profit,2)}"
            )

        # STOP LOSS
        elif profit <= -6:

            capital += btc * price
            btc = 0

            trades += 1
            losses += 1

            last_trade_time = now

            send_message(
                f"⚠️ STOP LOSS\nPreço: {price}\nPerda: {round(profit,2)}"
            )

    # =====================
    # ESTATÍSTICAS
    # =====================

    total = capital + btc * price

    winrate = 0
    if trades > 0:
        winrate = (wins / trades) * 100

    print("Capital:", round(total, 2))
    print("Trades:", trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("WinRate:", round(winrate, 2), "%")
