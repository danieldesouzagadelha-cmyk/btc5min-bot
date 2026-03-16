import time
import requests
from mercado import get_price
from strategy import trade
from telegram_bot import send_message


# pares padrão caso API falhe
default_pairs = [
"BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
"ADAUSDT","DOGEUSDT","AVAXUSDT","LTCUSDT","DOTUSDT",
"NEARUSDT","APTUSDT","ARBUSDT","INJUSDT","ATOMUSDT","SUIUSDT"
]


# =========================================
# PEGAR MOEDAS MAIS VOLÁTEIS DA MEXC
# =========================================

def get_most_volatile():

    try:

        url = "https://api.mexc.com/api/v3/ticker/24hr"
        data = requests.get(url, timeout=10).json()

        usdt_pairs = []

        for x in data:

            symbol = x["symbol"]

            if not symbol.endswith("USDT"):
                continue

            price = float(x["lastPrice"])

            # filtro anti shitcoin
            if price < 0.01:
                continue

            volatility = (float(x["highPrice"]) - float(x["lowPrice"])) / price

            usdt_pairs.append((symbol, volatility))

        sorted_pairs = sorted(usdt_pairs, key=lambda x: x[1], reverse=True)

        top10 = [x[0] for x in sorted_pairs[:10]]

        print("Top moedas voláteis:", top10)

        return top10

    except Exception as e:

        print("Erro ao pegar volatilidade:", e)
        send_message("⚠️ Erro ao pegar moedas voláteis, usando lista padrão")

        return default_pairs


# =========================================
# INICIO
# =========================================

print("===================================")
print(" MULTI COIN TREND PULLBACK BOT ")
print("===================================")

send_message("🤖 Bot iniciado e rodando na nuvem")

pairs = default_pairs
last_update = 0

loop = 0


while True:

    try:

        loop += 1
        print("Loop:", loop)

        # atualiza moedas a cada 15 minutos
        if time.time() - last_update > 900:

            pairs = get_most_volatile()
            last_update = time.time()

        for pair in pairs:

            try:

                data = get_price(pair)

                if data is None:
                    print("Erro ao pegar preço:", pair)
                    continue

                bid = data["bid"]
                ask = data["ask"]

                price = ask

                print(pair, "Bid:", bid, "Ask:", ask)

                trade(pair, price)

            except Exception as e:

                print("Erro na moeda", pair, e)

                send_message(f"⚠️ Erro na moeda {pair}: {e}")

        time.sleep(8)

    except Exception as e:

        print("Erro no loop principal:", e)

        send_message(f"⚠️ Erro no bot: {e}")

        time.sleep(5)
