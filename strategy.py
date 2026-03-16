import time
from telegram_bot import send_message
from exchange import create_order

# ======================================
#  CONFIGURAÇÕES - AJUSTE AQUI
# ======================================
capital = 49.0              # capital inicial em USDT
RISK_PER_TRADE = 0.015      # 1.5% do capital por trade (muito mais seguro)

# Parâmetros da estratégia
MIN_TREND_MOVE = 0.008      # mínimo +0.8% para considerar tendência de alta
PULLBACK_MIN   = -0.004     # retração mínima para entrar (-0.4%)
TP1_LEVEL      = 0.010      # +1.0% → fecha 50-60% da posição
TP2_LEVEL      = 0.025      # +2.5% → alvo final do restante
STOP_LOSS      = -0.006     # -0.6% inicial (mais respirável)
TRAIL_ACTIVATE = 0.012      # quando atingir +1.2%, ativa trailing
TRAIL_DISTANCE = 0.008      # trailing de -0.8% do preço atual

COOLDOWN_TIME  = 300        # 5 minutos entre entradas no mesmo par
EMA_PERIOD     = 21         # EMA simples para filtro de tendência

# Variáveis globais
positions = {}
state = {}                  # guarda last_price, trend_start, ema, etc.
trades = 0
wins = 0
losses = 0
cooldown = {}
last_trade_time = {}        # para limitar frequência geral (opcional)

def calculate_ema(price, prev_ema, period):
    """EMA simples recursiva (aproximação boa o suficiente)"""
    if prev_ema is None:
        return price
    multiplier = 2 / (period + 1)
    return price * multiplier + prev_ema * (1 - multiplier)

def trade(pair, price):
    global capital
    global trades, wins, losses

    now = time.time()

    # Inicializa estado do par na primeira vez
    if pair not in state:
        state[pair] = {
            "last_price": price,
            "trend_start": price,
            "ema": price,               # inicia EMA no primeiro preço
            "highest_since_entry": price
        }
        positions[pair] = None
        return

    # Atualiza EMA (filtro de tendência)
    state[pair]["ema"] = calculate_ema(price, state[pair]["ema"], EMA_PERIOD)
    ema = state[pair]["ema"]

    last_price = state[pair]["last_price"]
    trend_start = state[pair]["trend_start"]

    # Só opera se estiver em tendência de alta clara
    trend_strength = (price - trend_start) / trend_start
    is_bullish = price > ema and trend_strength > MIN_TREND_MOVE

    # Cooldown
    if pair in cooldown and now - cooldown[pair] < COOLDOWN_TIME:
        state[pair]["last_price"] = price
        return

    # ======================================
    #          ENTRADA (COMPRA)
    # ======================================
    if positions[pair] is None and is_bullish:

        pullback = (price - last_price) / last_price

        if pullback <= PULLBACK_MIN:

            # Calcula tamanho com risco fixo (% do capital)
            risk_amount = capital * RISK_PER_TRADE
            stop_distance = abs(STOP_LOSS)              # em decimal
            size = round(risk_amount / (price * stop_distance), 4)

            if size <= 0:
                return

            # COMPRA REAL
            create_order(pair, "BUY", size * price)     # valor em USDT

            positions[pair] = {
                "entry": price,
                "size": size,
                "partial_closed": False,
                "highest": price
            }

            cooldown[pair] = now
            print(f"BUY {pair} | size: {size:.4f} | entry: {price:.4f}")
            send_message(
                f"🟢 BUY {pair}\n"
                f"Preço: {round(price,4)}\n"
                f"Size: {size:.4f}\n"
                f"Capital: {round(capital,2)} USDT"
            )

    # ======================================
    #          GERENCIAMENTO DE POSIÇÃO
    # ======================================
    if positions[pair] is not None:

        pos = positions[pair]
        entry = pos["entry"]
        size = pos["size"]
        profit = (price - entry) / entry

        # Atualiza máxima desde a entrada (para trailing)
        if price > pos["highest"]:
            pos["highest"] = price

        # TAKE PROFIT PARCIAL (50% da posição)
        if profit >= TP1_LEVEL and not pos["partial_closed"]:
            sell_size = round(size * 0.5, 4)
            create_order(pair, "SELL", sell_size)
            
            pnl_partial = sell_size * (price - entry)
            capital += pnl_partial
            
            pos["size"] -= sell_size
            pos["partial_closed"] = True
            
            print(f"TP1 {pair} | partial {sell_size:.4f}")
            send_message(
                f"🟡 TP PARCIAL 50% {pair}\n"
                f"Preço: {round(price,4)}\n"
                f"Lucro parcial: {round(pnl_partial,4)} USDT\n"
                f"Restante: {pos['size']:.4f}\n"
                f"Capital: {round(capital,2)} USDT"
            )

        # TAKE PROFIT FINAL ou TRAILING
        do_exit = False
        exit_reason = ""

        if profit >= TP2_LEVEL:
            do_exit = True
            exit_reason = "TAKE PROFIT FINAL"

        elif profit >= TRAIL_ACTIVATE:
            # Trailing stop
            trail_stop = pos["highest"] * (1 - TRAIL_DISTANCE)
            if price <= trail_stop:
                do_exit = True
                exit_reason = "TRAILING STOP"

        elif profit <= STOP_LOSS:
            do_exit = True
            exit_reason = "STOP LOSS"

        if do_exit:
            create_order(pair, "SELL", pos["size"])
            pnl = pos["size"] * (price - entry)
            capital += pnl

            trades += 1
            if pnl > 0:
                wins += 1
            else:
                losses += 1

            print(f"{exit_reason} {pair} | pnl: {pnl:.4f}")
            send_message(
                f"{'🟢' if pnl > 0 else '⚠️'} {exit_reason} {pair}\n"
                f"Preço: {round(price,4)}\n"
                f"Resultado: {round(pnl,4)} USDT\n"
                f"Capital: {round(capital,2)} USDT"
            )

            winrate = (wins / trades * 100) if trades > 0 else 0
            send_message(
                f"📊 STATUS BOT\n"
                f"Capital: {round(capital,2)} USDT\n"
                f"Trades: {trades}\n"
                f"WinRate: {round(winrate,2)}%\n"
                f"W/L: {wins}/{losses}"
            )

            positions[pair] = None

    # Atualizações finais
    state[pair]["last_price"] = price

    # Reset de trend_start se preço cair significativamente
    if price < trend_start * 0.985:  # queda ~1.5% → reseta tendência
        state[pair]["trend_start"] = price
        state[pair]["ema"] = price   # reseta EMA também

    # Log simples no console
    total = capital
    winrate = (wins / trades * 100) if trades > 0 else 0
    print(f"[{pair}] Capital: {round(total,2)} | Trades: {trades} | WR: {round(winrate,1)}%")
