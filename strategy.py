import time
from telegram_bot import send_message

capital = 50

positions = {}
state = {}

trades = 0
wins = 0
losses = 0

cooldown = {}
COOLDOWN_TIME = 30

TREND_MOVE = 0.03
PULLBACK = 0.015

TAKE_PROFIT = 0.04
STOP_LOSS = -0.02


def trade(pair, price):

    global capital
    global trades
    global wins
    global losses

    now = time.time()

    if pair not in state:

        state[pair] = {
            "last_price": price,
            "trend_start": price
        }

        positions[pair] = None

        return

    last_price = state[pair]["last_price"]
    trend_start = state[pair]["trend_start"]

    move = price - trend_start

    # detectar tendência
    if move > TREND_MOVE:

        pullback = price - last_price

        # cooldown
        if pair in cooldown:
            if now - cooldown[pair] < COOLDOWN_TIME:
                return

        if pullback <= -PULLBACK and positions[pair] is None:

            size = 10 / price

            positions[pair] = {
                "entry": price,
                "size": size
            }

            cooldown[pair] = now

            print("BUY", pair)

            send_message(
    f"🟢 BUY {pair}\n"
    f"Preço: {round(price,4)}\n"
    f"Capital: {round(capital,2)} USDT"
)

    # saída
    if positions[pair] is not None:

        entry = positions[pair]["entry"]
        size = positions[pair]["size"]

        profit = price - entry

        # TAKE PROFIT
        if profit >= TAKE_PROFIT:

            pnl = size * (price - entry)

            capital += pnl

            positions[pair] = None

            trades += 1
            wins += 1

            print("TP", pair)

            send_message(
f"🔴 TAKE PROFIT {pair}\n"
f"Preço: {round(price,4)}\n"
f"Lucro: {round(pnl,2)} USDT\n"
f"Capital: {round(capital,2)} USDT"
)

send_message(
f"📊 STATUS BOT\n"
f"Capital: {round(capital,2)} USDT\n"
f"Trades: {trades}\n"
f"WinRate: {round(winrate,2)}%"
)

        # STOP LOSS
        elif profit <= STOP_LOSS:

            pnl = size * (price - entry)

            capital += pnl

            positions[pair] = None

            trades += 1
            losses += 1

            print("SL", pair)

            send_message(
    f"⚠️ STOP LOSS {pair}\n"
    f"Preço: {round(price,4)}\n"
    f"Resultado: {round(pnl,2)} USDT\n"
    f"Capital: {round(capital,2)} USDT"
)

    total = capital

    winrate = 0

    if trades > 0:
        winrate = (wins / trades) * 100

    print("Capital:", round(total, 2))
    print("Trades:", trades)
    print("WinRate:", round(winrate, 2))

    state[pair]["last_price"] = price

    # resetar tendência se preço cair
    if price < trend_start:
        state[pair]["trend_start"] = price
        
