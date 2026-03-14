from telegram_bot import send_message

capital = 50
btc = 0
entry_price = None

last_price = None
trend_start = None

trades = 0
wins = 0
losses = 0

# parâmetros da estratégia
TREND_MOVE = 20
PULLBACK = 6

TAKE_PROFIT = 12
STOP_LOSS = -8


def trade(price):

    global capital
    global btc
    global entry_price
    global last_price
    global trend_start
    global trades
    global wins
    global losses

    if last_price is None:
        last_price = price
        trend_start = price
        return

    move = price - trend_start

    # detectar tendência
    if move > TREND_MOVE:

        print("TREND DETECTADA")

        pullback = price - last_price

        # detectar correção
        if pullback <= -PULLBACK and btc == 0:

            btc = 10 / price
            capital -= 10
            entry_price = price

            print("BUY EXECUTADO")

            send_message(
                f"🟢 BUY BTC\nPreço: {price}"
            )

    # saída da posição
    if btc > 0:

        profit = price - entry_price

        if profit >= TAKE_PROFIT:

            capital += btc * price
            btc = 0

            trades += 1
            wins += 1

            print("TAKE PROFIT")

            send_message(
                f"🔴 TAKE PROFIT\nPreço: {price}"
            )

        elif profit <= STOP_LOSS:

            capital += btc * price
            btc = 0

            trades += 1
            losses += 1

            print("STOP LOSS")

            send_message(
                f"⚠️ STOP LOSS\nPreço: {price}"
            )

    total = capital + btc * price

    winrate = 0
    if trades > 0:
        winrate = (wins / trades) * 100

    print("Capital:", round(total, 2))
    print("Trades:", trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("WinRate:", round(winrate, 2))

    last_price = price
