import time
from telegram_bot import send_message
from exchange import create_order

# ============================================================
#  CONFIGURAÇÕES GERAIS
# ============================================================
capital = 49.0          # Banca inicial em USDT
trades = 0
wins = 0
losses = 0
daily_loss = 0.0
daily_loss_start = time.time()

positions = {}          # posições abertas por par
state = {}              # estado de preço/tendência por par
cooldown = {}           # cooldown por par

# ============================================================
#  PARÂMETROS DE ESTRATÉGIA
# ============================================================
TREND_MOVE       = 0.004   # 0.4% — movimento mínimo pra confirmar tendência
PULLBACK         = 0.002   # 0.2% — recuo mínimo pra entrar
TAKE_PROFIT      = 0.009   # 0.9% — alvo de lucro
STOP_LOSS        = -0.004  # 0.4% — stop de perda

# ============================================================
#  TRAILING STOP
# ============================================================
TRAILING_ACTIVATION = 0.005  # ativa trailing após 0.5% de lucro
TRAILING_DISTANCE   = 0.003  # mantém 0.3% abaixo do topo

# ============================================================
#  GESTÃO DE BANCA
# ============================================================
RISK_PERCENT       = 0.15   # 15% da banca por trade (~$7.35)
MAX_POSITIONS      = 3      # máximo de posições abertas ao mesmo tempo
DAILY_LOSS_LIMIT   = 0.15   # para o bot se perder 15% da banca no dia
MIN_VOLUME_USDT    = 1_000_000  # volume mínimo do par em 24h (USDT)

# ============================================================
#  COOLDOWN
# ============================================================
COOLDOWN_TIME = 30  # segundos entre trades no mesmo par

# ============================================================
#  PARES OPERADOS
# ============================================================
PAIRS = [
    "SOLUSDT",
    "DOGEUSDT",
    "XRPUSDT",
    "BNBUSDT",
]

# ============================================================
#  HELPERS
# ============================================================

def get_trade_value():
    """Tamanho do trade dinâmico: 15% da banca atual."""
    return round(capital * RISK_PERCENT, 2)


def positions_open():
    """Retorna quantas posições estão abertas agora."""
    return sum(1 for p in positions.values() if p is not None)


def reset_daily_loss_if_needed():
    """Reseta o contador de perda diária a cada 24h."""
    global daily_loss, daily_loss_start
    if time.time() - daily_loss_start >= 86400:
        daily_loss = 0.0
        daily_loss_start = time.time()
        send_message("🔄 Novo dia — contador de perda diária resetado.")


def daily_limit_reached():
    """Verifica se o limite de perda diária foi atingido."""
    limit = capital * DAILY_LOSS_LIMIT
    if daily_loss >= limit:
        send_message(
            f"🛑 LIMITE DIÁRIO ATINGIDO\n"
            f"Perda acumulada: {round(daily_loss, 2)} USDT\n"
            f"Bot pausado até amanhã."
        )
        return True
    return False


def send_status():
    """Envia status geral pelo Telegram."""
    winrate = round((wins / trades) * 100, 2) if trades > 0 else 0.0
    send_message(
        f"📊 STATUS BOT\n"
        f"Capital: {round(capital, 2)} USDT\n"
        f"Trades: {trades}\n"
        f"Wins: {wins} | Losses: {losses}\n"
        f"WinRate: {winrate}%\n"
        f"Perda hoje: {round(daily_loss, 2)} USDT"
    )


# ============================================================
#  FECHAR POSIÇÃO (TP / SL / TRAILING)
# ============================================================

def close_position(pair, price, reason):
    global capital, trades, wins, losses, daily_loss

    pos   = positions[pair]
    entry = pos["entry"]
    size  = pos["size"]
    trade_value = pos["trade_value"]

    pnl = size * (price - entry)
    capital += trade_value + pnl   # devolve o capital + lucro/prejuízo
    positions[pair] = None
    trades += 1

    # Reseta tendência pra evitar re-entrada imediata
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
        f"Entrada: {round(entry, 4)}\n"
        f"Saída:   {round(price, 4)}\n"
        f"Resultado: {round(pnl, 4)} USDT\n"
        f"Capital: {round(capital, 2)} USDT"
    )
    send_status()


# ============================================================
#  FUNÇÃO PRINCIPAL DE TRADE
# ============================================================

def trade(pair, price, volume_24h=None):
    global capital

    # --- Filtro de volume mínimo ---
    if volume_24h is not None and volume_24h < MIN_VOLUME_USDT:
        return

    # --- Proteções globais ---
    reset_daily_loss_if_needed()
    if daily_limit_reached():
        return

    now = time.time()

    # --- Inicialização do par ---
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
    peak_price  = state[pair].get("peak_price", price)
    move        = (price - trend_start) / trend_start

    # --------------------------------------------------------
    #  LÓGICA DE ENTRADA
    # --------------------------------------------------------
    if positions[pair] is None:
        in_cooldown   = pair in cooldown and (now - cooldown[pair] < COOLDOWN_TIME)
        slots_ok      = positions_open() < MAX_POSITIONS
        trade_value   = get_trade_value()
        capital_ok    = trade_value <= capital

        if move > TREND_MOVE and not in_cooldown and slots_ok and capital_ok:
            pullback_pct = (price - last_price) / last_price

            if pullback_pct <= -PULLBACK:
                size = round(trade_value / price, 6)

                create_order(pair, "BUY", trade_value)
                capital -= trade_value  # debita o capital

                positions[pair] = {
                    "entry":       price,
                    "size":        size,
                    "trade_value": trade_value,
                    "peak_price":  price,
                    "trailing_on": False,
                }
                cooldown[pair] = now

                print(f"🟢 BUY {pair} | Preço: {price} | Valor: {trade_value} | Capital: {round(capital,2)}")
                send_message(
                    f"🟢 BUY {pair}\n"
                    f"Preço: {round(price, 4)}\n"
                    f"Valor: {trade_value} USDT\n"
                    f"Capital restante: {round(capital, 2)} USDT\n"
                    f"Posições abertas: {positions_open()}/{MAX_POSITIONS}"
                )

    # --------------------------------------------------------
    #  LÓGICA DE SAÍDA
    # --------------------------------------------------------
    elif positions[pair] is not None:
        pos    = positions[pair]
        entry  = pos["entry"]
        profit = (price - entry) / entry

        # Atualiza o pico de preço
        if price > pos["peak_price"]:
            pos["peak_price"] = price

        # Ativa o trailing stop
        if profit >= TRAILING_ACTIVATION:
            pos["trailing_on"] = True

        # Verifica trailing stop
        if pos["trailing_on"]:
            peak    = pos["peak_price"]
            drawdown = (price - peak) / peak
            if drawdown <= -TRAILING_DISTANCE:
                create_order(pair, "SELL", pos["size"])
                capital += pos["trade_value"]   # será recalculado em close_position
                capital -= pos["trade_value"]   # ajuste — close_position adiciona tudo
                close_position(pair, price, "TRAILING")
                return

        # Take Profit fixo
        if profit >= TAKE_PROFIT:
            create_order(pair, "SELL", pos["size"])
            close_position(pair, price, "TP")
            return

        # Stop Loss fixo
        if profit <= STOP_LOSS:
            create_order(pair, "SELL", pos["size"])
            close_position(pair, price, "SL")
            return

    # --------------------------------------------------------
    #  ATUALIZA ESTADO
    # --------------------------------------------------------
    state[pair]["last_price"] = price

    # Atualiza pico da posição aberta
    if positions[pair] is not None and price > positions[pair]["peak_price"]:
        positions[pair]["peak_price"] = price

    # Reseta tendência se preço cair abaixo do início
    if price < trend_start:
        state[pair]["trend_start"] = price

    # Debug no console
    winrate = round((wins / trades) * 100, 2) if trades > 0 else 0
    print(
        f"[{pair}] {round(price,4)} | "
        f"Capital: {round(capital,2)} | "
        f"Trades: {trades} | "
        f"WR: {winrate}% | "
        f"Posições: {positions_open()}/{MAX_POSITIONS}"
    )


# ============================================================
#  LOOP PRINCIPAL (exemplo de integração)
# ============================================================

def run():
    send_message(
        f"🤖 BOT INICIADO\n"
        f"Banca: {capital} USDT\n"
        f"Pares: {', '.join(PAIRS)}\n"
        f"TP: {TAKE_PROFIT*100}% | SL: {abs(STOP_LOSS)*100}%\n"
        f"Trailing ativa após: {TRAILING_ACTIVATION*100}%\n"
        f"Max posições: {MAX_POSITIONS}"
    )

    while True:
        for pair in PAIRS:
            try:
                # Substitua pelo seu método de obter preço e volume da MEXC
                # price    = exchange.get_price(pair)
                # volume   = exchange.get_volume_24h(pair)
                # trade(pair, price, volume)
                pass
            except Exception as e:
                print(f"ERRO {pair}: {e}")
                send_message(f"❌ ERRO em {pair}: {e}")

        time.sleep(1)  # 1 tick por segundo


if __name__ == "__main__":
    run()
