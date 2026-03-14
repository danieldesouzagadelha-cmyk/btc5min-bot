import time
from telegram_bot import send_message

capital = 50
btc = 0

position_price = None

last_trade_time = 0
cooldown_seconds = 60

trades = 0
wins = 0
losses = 0

def trade(price):

    global capital
    global btc
    global position_price
    global last_trade_time
    global trades
    global wins
    global losses

    now = time.time()

    if now - last_trade_time < cooldown_seconds:
        print("Cooldown ativo")
        return

    # BUY
    if btc == 0 and capital >= 10:

        btc = 10 / price
        capital -= 10
        position_price = price

        last_trade_time = now

        print("BUY:", price)

        send_message(f"🟢 BUY BTC\nPreço: {price}")

        return

    # SELL
    if btc > 0:

        profit = price - position_price

        if abs(profit) > 15:

            capital += btc * price
            btc = 0

            trades += 1

            if profit > 0:
                wins += 1
            else:
                losses += 1

            last_trade_time = now

            total = capital

            msg = f"""
🔴 SELL BTC

Preço: {price}
Lucro trade: {round(profit,2)}

Trades: {trades}
Wins: {wins}
Losses: {losses}

Capital: {round(total,2)}
"""

            print(msg)

            send_message(msg)
