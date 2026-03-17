import time
from telegram_bot import send_message
from exchange import create_order

# ============================================================
#  CONFIGURAÇÕES — igual ao seu original
# ============================================================
capital       = 79.0   # banca atual
positions     = {}
state         = {}
trades        = 0
wins          = 0
losses        = 0
cooldown      = {}

COOLDOWN_TIME = 30
TREND_MOVE    = 0.004
PULLBACK      = 0.002
TAKE_PROFIT   = 0.007
STOP_LOSS     = -0.003
TRADE_VALUE   = 7       # fixo em USDT por trade — igual ao seu original


# ============================================================
#  FUNÇÃO PRINCIPAL — sua lógica original preservada
# ============================================================

def trade(pair, price):
    global capital, trades, wins, losses
    now = time.time()

    if pair not in state:
        state[pair] = {
            "last_price":  price,
            "trend_start": price
        }
        positions[pair] = None
        return

    last_price  = state[pair]["last_price"]
    trend_start = state[pair]["trend_start"]
    move        = (price - trend_start) / trend_start

    # ── ENTRADA ─────────────────────────────────────────────
    if move > TREND_MOVE:
        pullback = price - last_price

        if pair in cooldown:
            if now - cooldown[pair] < COOLDOWN_TIME:
                # atualiza estado e sai
                state[pair]["last_price"] = price
                if price < trend_start:
                    state[pair]["trend_start"] = price
                return

        if pullback <= -PULLBACK and positions[pair] is None:

            # ✅ ÚNICA CORREÇÃO: size com mais precisão (6 casas)
            #    BUY e SELL usam a mesma variável size
            size = round(TRADE_VALUE / price, 6)

            # ✅ CORRIGIDO: BUY envia size (quantidade) não USDT
            create_order(pair, "BUY", size)

            positions[pair] = {
                "entry": price,
                "size":  size
            }
            cooldown[pair] = now

            print("BUY", pair)
            send_message(
                f"🟢 BUY {pair}\n"
                f"Preço: {round(price, 4)}\n"
                f"Quantidade: {size}\n"
                f"Capital: {round(capital, 2)} USDT"
            )

    # ── SAÍDA ────────────────────────────────────────────────
    if positions[pair] is not None:
        entry  = positions[pair]["entry"]
        size   = positions[pair]["size"]
        profit = (price - entry) / entry

        # TAKE PROFIT
        if profit >= TAKE_PROFIT:
            # ✅ SELL com mesma quantidade do BUY
            create_order(pair, "SELL", size)
            pnl     = size * (price - entry)
            capital += pnl
            positions[pair] = None
            trades += 1
            wins   += 1
            print("TP", pair)
            send_message(
                f"🔴 TAKE PROFIT {pair}\n"
                f"Preço: {round(price, 4)}\n"
                f"Lucro: {round(pnl, 4)} USDT\n"
                f"Capital: {round(capital, 2)} USDT"
            )
            winrate = (wins / trades) * 100
            send_message(
                f"📊 STATUS BOT\n"
                f"Capital: {round(capital, 2)} USDT\n"
                f"Trades: {trades}\n"
                f"WinRate: {round(winrate, 2)}%"
            )

        # STOP LOSS
        elif profit <= STOP_LOSS:
            # ✅ SELL com mesma quantidade do BUY
            create_order(pair, "SELL", size)
            pnl     = size * (price - entry)
            capital += pnl
            positions[pair] = None
            trades += 1
            losses += 1
            print("SL", pair)
            send_message(
                f"⚠️ STOP LOSS {pair}\n"
                f"Preço: {round(price, 4)}\n"
                f"Resultado: {round(pnl, 4)} USDT\n"
                f"Capital: {round(capital, 2)} USDT"
            )
            winrate = (wins / trades) * 100
            send_message(
                f"📊 STATUS BOT\n"
                f"Capital: {round(capital, 2)} USDT\n"
                f"Trades: {trades}\n"
                f"WinRate: {round(winrate, 2)}%"
            )

    # ── DEBUG CONSOLE ────────────────────────────────────────
    winrate = (wins / trades) * 100 if trades > 0 else 0
    print("Capital:", round(capital, 2))
    print("Trades:", trades)
    print("WinRate:", round(winrate, 2))

    # ── ATUALIZA ESTADO ──────────────────────────────────────
    state[pair]["last_price"] = price
    if price < trend_start:
        state[pair]["trend_start"] = price


# ============================================================
#  STATUS — chamado pelo bot.py a cada 1 hora
# ============================================================

def send_status():
    winrate = round((wins / trades) * 100, 2) if trades > 0 else 0.0
    send_message(
        f"📊 STATUS BOT\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Capital: {round(capital, 2)} USDT\n"
        f"📈 Trades: {trades}\n"
        f"✅ Wins: {wins} | ❌ Losses: {losses}\n"
        f"🎯 WinRate: {winrate}%"
    )
