import requests
import os

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_message(text):

    print("Enviando mensagem para Telegram...")

    if not BOT_TOKEN or not CHAT_ID:
        print("TOKEN ou CHAT_ID não encontrados")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": text
    }

    response = requests.post(url, data=data)

    print("Resposta Telegram:", response.text)
