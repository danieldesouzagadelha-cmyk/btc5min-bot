import time
from mercado import get_price
from strategy import trade
from telegram_bot import send_message


pairs = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "ADAUSDT",
    "LINKUSDT"
]


print("===================================")
print(" MULTI COIN TREND PULLBACK BOT ")
print("===================================")

# envia mensagem quando inicia
send_message("🤖 Bot iniciado e rodando na nuvem")

loop = 0

while True:

    try:

        loop += 1
        print("Loop:", loop)

        for pair in pairs:

            try:

                price = get_price(pair)

                if price is None:
                    print("Erro ao pegar preço:", pair)
                    continue

                # mostra preço no log
                print(pair, "Preço:", price)

                trade(pair, price)

            except Exception as e:

                print("Erro na moeda", pair, e)

                send_message(f"⚠️ Erro na moeda {pair}: {e}")

        time.sleep(8)

    except Exception as e:

        print("Erro no loop principal:", e)

        send_message(f"⚠️ Erro no bot: {e}")

        time.sleep(5)
