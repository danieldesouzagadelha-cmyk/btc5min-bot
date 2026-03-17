import time
from mercado import get_price
from strategy import trade, capital, send_status
from telegram_bot import send_message

# ============================================================
#  PARES — seus originais
# ============================================================
pairs = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "LINKUSDT",
]

# ============================================================
#  INICIO
# ============================================================
print("===================================")
print("   MULTI COIN TREND PULLBACK BOT   ")
print("===================================")

send_message(
    f"🤖 Bot iniciado!\n"
    f"📌 Pares: {', '.join(pairs)}\n"
    f"💰 Banca: {capital} USDT\n"
    f"⚙️ TP: 0.7% | SL: 0.3%\n"
    f"💸 Trade fixo: $7 USDT"
)

# ============================================================
#  LOOP PRINCIPAL
# ============================================================
loop = 0
last_status_time = time.time()
STATUS_INTERVAL  = 3600  # status a cada 1 hora

while True:
    try:
        loop += 1
        print(f"\n{'='*40}")
        print(f"Loop: {loop}")
        print(f"{'='*40}")

        for pair in pairs:
            try:
                data = get_price(pair)

                if data is None:
                    print(f"⚠️  Erro ao pegar preço: {pair}")
                    continue

                bid   = data["bid"]
                ask   = data["ask"]
                price = ask

                print(f"{pair:12} | Bid: {bid} | Ask: {ask}")

                trade(pair, price)

            except Exception as e:
                print(f"Erro na moeda {pair}: {e}")
                send_message(f"⚠️ Erro na moeda {pair}: {e}")

        # status automático a cada 1 hora
        if time.time() - last_status_time >= STATUS_INTERVAL:
            send_status()
            last_status_time = time.time()

        time.sleep(8)

    except Exception as e:
        print(f"Erro no loop principal: {e}")
        send_message(f"⚠️ Erro no bot: {e}")
        time.sleep(5)
