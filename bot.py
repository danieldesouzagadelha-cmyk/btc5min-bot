
#!/usr/bin/env python3
"""
=================================================================
    BOT DE TESTE - VERSÃO MÍNIMA
    Apenas para confirmar que o deploy funciona
=================================================================
"""

import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TESTE] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("Teste")

# Lê variáveis (não usa para nada, só para testar)
SIMULATION = os.getenv("SIMULATION_MODE", "true")
CAPITAL = os.getenv("CAPITAL", "50.0")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "não configurado")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "não configurado")
WALLET = os.getenv("WALLET_ADDRESS", "não configurado")
KEY = os.getenv("PRIVATE_KEY", "não configurado")  # ← ISSO NÃO CAUSA ERRO

print("\n" + "="*60)
print(" BOT DE TESTE - VERSÃO MÍNIMA")
print("="*60)
print(f" Início: {datetime.now()}")
print(f" Modo: {SIMULATION}")
print(f" Capital: {CAPITAL}")
print(f" Telegram Token: {TOKEN[:5]}..." if len(TOKEN) > 5 else " Telegram Token: não")
print(f" Wallet: {WALLET[:10]}..." if len(WALLET) > 10 else " Wallet: não")
print(f" Private Key: {'✅ configurada' if len(KEY) > 10 else '❌ não configurada'}")
print("="*60 + "\n")

contador = 0
while True:
    try:
        contador += 1
        log.info(f"Heartbeat #{contador} - {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(30)
    except KeyboardInterrupt:
        break
