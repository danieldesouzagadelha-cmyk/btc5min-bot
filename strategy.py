import time
from telegram_bot import send_message
from exchange import create_order

# ============================================================
#  CONFIGURAÇÕES GERAIS
# ============================================================
capital          = 55.0
trades           = 0
wins             = 0
losses           = 0
daily_loss       = 0.0
daily_loss_start = time.time()

positions = {}
state     = {}
cooldown  = {}

# ============================================================
#  PARÂMETROS DE ESTRATÉGIA
# ============================================================
TREND_MOVE  = 0.004   # 0.4% pra confirmar tendência de alta
PULLBACK    = 0.002   # 0.2% de recuo mínimo pra entrar
TAKE_PROFIT = 0.009   # 0.9% alvo de lucro
STOP_LOSS   = -0.004  # 0.4% stop de perda

# ============================================================
#  TRAILING STOP
# ============================================================
TRAILING_ACTIVATION = 0.005  # ativa trailing após 0.5% de lucro
TRAILING_DISTANCE   = 0.003  # sai se cair 0.3% do topo

# ============================================================
#  GESTÃO DE BANCA
# ============================================================
RISK_PERCENT     = 0.07  # ✅ CORRIGIDO: 7% por trade (~$5.50) — mais seguro
MAX_POSITIONS    = 3     # máximo de posições simultâneas
DAILY_LOSS_LIMIT = 0.15  # para o bot se perder 15% da banca no dia
COOLDOWN_TIME    = 30    # segundos entre trades no mesmo par

# ============================================================
#  FILTRO DE SPREAD
# ============================================================
MAX_SPREAD_PCT = 0.0005  # spread máximo permitido: 0.05%


# ============================================================
#  HELPERS
# ============================================================

def get_trade_value():
    """Trade dinâmico: 7% da banca atual."""
    return round(capital * RISK_PERCENT, 2)


def positions_open():
    """Quantas posições estão abertas agora."""
    return sum(1 for p in positions.values() if p is not None)


def reset_daily_loss_if_needed():
    global daily_loss, daily_loss_start
    if time.time() - daily_loss_start >= 86400:
        daily_loss       = 0.0
        daily_loss_start = time.time()
        send_message("🔄 Novo dia — contador de perda diária resetado.")


def daily_limit_reached():
    limit = capital * DAILY_LOSS_LIMIT
    if daily_loss >= limit:
        send_message(
            f"🛑 LIMITE DIÁRIO ATINGIDO\n"
            f"Perda acumulada: {round(daily_loss, 2)} USDT\n"
            f"Bot pausado até amanhã."
        )
        return True
    return False


def spread_ok(bid, ask):
    """
    ✅ NOVO — Filtro de spread.
    Evita entrar em mercado ilíquido ou com spread alto.
    """
    if bid is None or ask is None or bid == 0:
        return False
    spread_pct = (ask - bid) / bid
    return spread_pct <= MAX_SPREAD_PCT


def send_status():
    """Envia status completo pelo Telegram."""
    winrate = round((wins / trades) * 100, 2) if trades > 0 else 0.0
    send_message(
        f"📊 STATUS BOT\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Capital: {round(capital, 2)} USDT\n"
        f"📈 Trades: {trades}\n"
        f"✅ Wins: {wins} | ❌ Losses: {losses}\n"
        f"🎯 WinRate: {winrate}%\n"
        f"📌 Posições: {positions_open()}/{MAX_POSITIONS}\n"
        f"🔻 Perda hoje: {round(daily_loss, 2)} USDT"
    )


# ============================================================
#  FECHAR POSIÇÃO (TP / SL / TRAILING)
# ============================================================

def close_position(pair, price, reason):
    global capital, trades, wins, losses, daily_loss

    pos         = positions[pair]
    entry       = pos["entry"]
    size        = pos["size"]
    trade_value = pos["trade_value"]

    pnl     = size * (price - entry)
    capital += trade_value + pnl
    positions[pair] = None
    trades += 1

    # reseta tendência pra evitar re-entrada imediata
    state[pair]["trend_start"] = price
    state[pair]["last_price"]  = price
    state[pair]["peak_price"]  = price

    if reason in ("TP", "TRAILING"):
        wins += 1
        icon  = "🔴" if reason == "TP" else "📈"
        label = "TAKE PROFIT" if reason == "TP" else "TRAILING STOP"
    else:
        losses += 1
        daily_loss += abs(pnl)
        icon  = "⚠️"
        label = "STOP LOSS"

    print(f"{reason} {pair} | PnL: {round(pnl,4)} | Capital: {round(capital,2)}")

    send_message(
        f"{icon} {label} {pair}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Entrada: {round(entry, 6)}\n"
        f"Saída:   {round(price, 6)}\n"
        f"Resultado: {round(pnl, 4)} USDT\n"
        f"💰 Capital: {round(capital, 2)} USDT"
    )
    send_status()


# ============================================================
#  FUNÇÃO PRINCIPAL
# ============================================================

def trade(pair, price, bid=None, ask=None):
    global capital

    reset_daily_loss_if_needed()
    if daily_limit_reached():
        return

    now = time.time()

    # inicialização do par na primeira chamada
    if pair not in state:
        state[pair] = {
            "last_price":  price,
            "trend_start": price,
            "peak_price":  price,
        }
        positions[pair] = None
        return

    last_price  = state[pair]["last_price"]
    trend_start = state[pair]["trend_start"]
    move        = (price - trend_start) / trend_start

    # --------------------------------------------------------
    #  ENTRADA
    # --------------------------------------------------------
    if positions[pair] is None:
        in_cooldown = pair in cooldown and (now - cooldown[pair] < COOLDOWN_TIME)
        slots_ok    = positions_open() < MAX_POSITIONS
        trade_value = get_trade_value()
        capital_ok  = trade_value <= capital

        # ✅ NOVO — filtro de spread antes de entrar
        spread_valido = spread_ok(bid, ask) if bid and ask else True

        if move > TREND_MOVE and not in_cooldown and slots_ok and capital_ok and spread_valido:
            pullback_pct = (price - last_price) / last_price

            if pullback_pct <= -PULLBACK:
                # ✅ CORRIGIDO: calcula size ANTES e usa em BUY e SELL
                size = round(trade_value / price, 6)

                # ✅ CORRIGIDO: BUY com quantidade (size), não com USDT
                create_order(pair, "BUY", size)
                capital -= trade_value

                positions[pair] = {
                    "entry":       price,
                    "size":        size,
                    "trade_value": trade_value,
                    "peak_price":  price,
                    "trailing_on": False,
                }
                cooldown[pair] = now

                print(f"🟢 BUY {pair} | Preço: {price} | Size: {size} | Valor: {trade_value} USDT | Capital: {round(capital,2)}")
                send_message(
                    f"🟢 BUY {pair}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"Preço: {round(price, 6)}\n"
                    f"Quantidade: {size}\n"
                    f"Valor: {trade_value} USDT\n"
                    f"💰 Capital restante: {round(capital, 2)} USDT\n"
                    f"📌 Posições: {positions_open()}/{MAX_POSITIONS}"
                )

    # --------------------------------------------------------
    #  SAÍDA
    # --------------------------------------------------------
    elif positions[pair] is not None:
        pos    = positions[pair]
        entry  = pos["entry"]
        profit = (price - entry) / entry

        # atualiza pico de preço
        if price > pos["peak_price"]:
            pos["peak_price"] = price

        # ativa trailing stop
        if profit >= TRAILING_ACTIVATION:
            pos["trailing_on"] = True

        # verifica trailing stop
        if pos["trailing_on"]:
            peak     = pos["peak_price"]
            drawdown = (price - peak) / peak
            if drawdown <= -TRAILING_DISTANCE:
                # ✅ SELL com a mesma quantidade do BUY
                create_order(pair, "SELL", pos["size"])
                close_position(pair, price, "TRAILING")
                return

        # take profit fixo
        if profit >= TAKE_PROFIT:
            # ✅ SELL com a mesma quantidade do BUY
            create_order(pair, "SELL", pos["size"])
            close_position(pair, price, "TP")
            return

        # stop loss fixo
        if profit <= STOP_LOSS:
            # ✅ SELL com a mesma quantidade do BUY
            create_order(pair, "SELL", pos["size"])
            close_position(pair, price, "SL")
            return

    # --------------------------------------------------------
    #  ATUALIZA ESTADO
    # --------------------------------------------------------
    state[pair]["last_price"] = price

    if positions[pair] is not None and price > positions[pair]["peak_price"]:
        positions[pair]["peak_price"] = price

    # reseta tendência se preço cair abaixo do início
    if price < trend_start:
        state[pair]["trend_start"] = price

    winrate = round((wins / trades) * 100, 2) if trades > 0 else 0
    print(
        f"[{pair}] {round(price, 4)} | "
        f"Capital: {round(capital, 2)} | "
        f"Trades: {trades} | "
        f"WR: {winrate}% | "
        f"Posições: {positions_open()}/{MAX_POSITIONS}"
    )
