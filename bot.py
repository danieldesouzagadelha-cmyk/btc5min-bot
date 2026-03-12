
#!/usr/bin/env python3
"""
=================================================================
    BTC 5 MIN BOT - VERSÃO SIMPLIFICADA QUE FUNCIONA
    Sem frescura - monitora e opera nos últimos 10 segundos
=================================================================
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuração
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BTC5M] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("BTC5M")

# Config
BINANCE_URL = "https://api.binance.com/api/v3/klines"
SIMULATION = True
BANKROLL = 100.0

def get_btc_price():
    """Pega preço atual do BTC"""
    try:
        url = f"{BINANCE_URL}?symbol=BTCUSDT&interval=1m&limit=1"
        r = requests.get(url, timeout=2)
        return float(r.json()[0][4])
    except:
        return None

def get_window_info():
    """Retorna informações da janela atual de 5 minutos"""
    now = int(time.time())
    start = now - (now % 300)
    end = start + 300
    elapsed = now - start
    remaining = end - now
    
    return {
        "start": start,
        "end": end,
        "elapsed": elapsed,
        "remaining": remaining,
        "start_time": datetime.fromtimestamp(start).strftime("%H:%M:%S"),
        "end_time": datetime.fromtimestamp(end).strftime("%H:%M:%S")
    }

def get_open_price(window_start):
    """Pega preço de abertura da janela"""
    try:
        url = f"{BINANCE_URL}?symbol=BTCUSDT&interval=1m&startTime={window_start*1000}&limit=1"
        r = requests.get(url, timeout=2)
        return float(r.json()[0][4])
    except:
        return None

# Loop principal
log.info("="*60)
log.info(" BTC 5 MIN BOT - VERSÃO SIMPLIFICADA")
log.info("="*60)
log.info(f" Modo: {'SIMULAÇÃO' if SIMULATION else 'REAL'}")
log.info(f" Bankroll: ${BANKROLL}")
log.info("="*60)

ultima_janela = 0
ciclo = 0

while True:
    try:
        ciclo += 1
        window = get_window_info()
        
        # Nova janela
        if window["start"] != ultima_janela:
            ultima_janela = window["start"]
            log.info(f"\n{'='*60}")
            log.info(f"⏰ JANELA: {window['start_time']} - {window['end_time']}")
        
        # Mostra heartbeat a cada 10 segundos
        if ciclo % 10 == 0:
            log.info(f"💓 Heartbeat - Restam: {window['remaining']}s")
        
        # Só nos últimos 10 segundos
        if window["remaining"] <= 10:
            open_price = get_open_price(window["start"])
            current_price = get_btc_price()
            
            if open_price and current_price:
                diff = ((current_price - open_price) / open_price) * 100
                log.info(f"🔍 ÚLTIMOS {window['remaining']}s - BTC: ${current_price:.2f} | Diff: {diff:+.3f}%")
                
                # Estratégia: se subiu >0.08%, compra UP
                if diff > 0.08:
                    log.info(f"🎯 OPORTUNIDADE: UP com {diff:.2f}% de movimento")
                    log.info(f"💰 TRADE SIMULADO: Comprou UP @ ${current_price:.2f}")
                
                # Se caiu >0.08%, compra DOWN
                elif diff < -0.08:
                    log.info(f"🎯 OPORTUNIDADE: DOWN com {diff:.2f}% de movimento")
                    log.info(f"💰 TRADE SIMULADO: Comprou DOWN @ ${current_price:.2f}")
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        log.info("\n🛑 Bot parado")
        break
    except Exception as e:
        log.error(f"Erro: {e}")
        time.sleep(5)

