import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_message(text):

    if not TOKEN or not CHAT_ID:
        print("Telegram não configurado")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Erro Telegram:", e)
