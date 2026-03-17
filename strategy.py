import time
from telegram_bot import send_message
from exchange import create_order

capital = 79.0
positions = {}
state = {}
trades = 0
wins = 0
losses = 0
cooldown = {}

COOLDOWN_TIME = 30
TREND_MOVE = 0.004
PULLBACK = 0.002
TAKE_PROFIT = 0.007
STOP_LOSS = -0.003
TRADE_VALUE = 7


def trade(pair, price):

    global capital, trades, wins, losses

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

    move = (price - trend_start) / trend_start


    if move > TREND_MOVE:

        pullback = price - last_price

        if pair in cooldown:

            if now - cooldown[pair] < COOLDOWN_TIME:

                state[pair]["last_price"] = price
                return


        if pullback <= -PULLBACK and positions[pair] is None:

            size = round(TRADE_VALUE / price, 6)

            create_order(pair, "BUY", size)

            positions[pair] = {
                "entry": price,
                "size": size
            }

            cooldown[pair] = now

            send_message(
                f"🟢 BUY {pair}\n"
                f"Preço: {round(price,4)}\n"
                f"Qtd: {size}"
            )


    if positions[pair] is not None:

        entry = positions[pair]["entry"]
        size = positions[pair]["size"]

        profit = (price - entry) / entry


        if profit >= TAKE_PROFIT:

            create_order(pair, "SELL", size)

            pnl = size * (price - entry)

            capital += pnl

            positions[pair] = None

            trades += 1
            wins += 1

            send_message(
                f"🎯 TAKE PROFIT {pair}\n"
                f"Lucro: {round(pnl,4)} USDT"
            )


        elif profit <= STOP_LOSS:

            create_order(pair, "SELL", size)

            pnl = size * (price - entry)

            capital += pnl

            positions[pair] = None

            trades += 1
            losses += 1

            send_message(
                f"⚠️ STOP LOSS {pair}\n"
                f"Resultado: {round(pnl,4)} USDT"
            )


    state[pair]["last_price"] = price

    if price < trend_start:
        state[pair]["trend_start"] = price


def send_status():

    winrate = (wins / trades) * 100 if trades > 0 else 0

    send_message(
        f"📊 STATUS BOT\n"
        f"Capital: {round(capital,2)}\n"
        f"Trades: {trades}\n"
        f"WinRate: {round(winrate,2)}%"
    )
