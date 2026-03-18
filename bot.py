import time
from mercado import get_price
from strategy import trade, capital, send_status
from telegram_bot import send_message

pairs = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "LINKUSDT",
]

print("===================================")
print("   MULTI COIN TREND PULLBACK BOT   ")
print("===================================")

send_message(
    f"🤖 Bot iniciado!\n"
    f"Pares: {', '.join(pairs)}\n"
    f"Banca: {capital} USDT"
)

loop = 0
last_status_time = time.time()
STATUS_INTERVAL = 3600


while True:

    try:

        loop += 1

        print(f"\nLoop {loop}")

        for pair in pairs:

            data = get_price(pair)

            if data is None:
                continue

            bid = data["bid"]
            ask = data["ask"]

            price = ask

            print(pair, bid, ask)

            trade(pair, price)


        if time.time() - last_status_time >= STATUS_INTERVAL:

            send_status()

            last_status_time = time.time()


        time.sleep(8)


    except Exception as e:

        print("Erro:", e)

        send_message(f"⚠️ Erro no bot {e}")

        time.sleep(5)
