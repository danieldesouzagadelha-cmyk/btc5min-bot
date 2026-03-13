#!/usr/bin/env python3
"""
=================================================================
    FARM BOT - VERSÃO SIMPLIFICADA
    Teste de conectividade - 100% funcional
=================================================================
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BOT] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("Bot")

# ============= CONFIGURAÇÕES BÁSICAS =============
class Config:
    # Modo de operação (sempre simulação por enquanto)
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    CAPITAL = float(os.getenv("CAPITAL", "50.0"))

config = Config()

# ============= FUNÇÃO PRINCIPAL =============
def testar_api_polymarket():
    """Testa se consegue conectar na API da Polymarket"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "active": "true",
            "limit": 5
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            markets = resp.json()
            log.info(f"✅ Conectado à Polymarket! {len(markets)} mercados encontrados")
            return True
        else:
            log.error(f"❌ Erro na API: {resp.status_code}")
            return False
    except Exception as e:
        log.error(f"❌ Erro de conexão: {e}")
        return False

# ============= BOT PRINCIPAL =============
class SimpleBot:
    def __init__(self):
        self.running = True
        self.heartbeat = 0
        
        log.info("\n" + "="*60)
        log.info(" FARM BOT - VERSÃO SIMPLIFICADA")
        log.info("="*60)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Capital: ${config.CAPITAL}")
        log.info("="*60)
    
    def run(self):
        """Loop principal"""
        log.info("\n🚀 BOT INICIADO - TESTANDO CONEXÕES...\n")
        
        # Testa API da Polymarket
        testar_api_polymarket()
        
        log.info("\n✅ Testes concluídos. Iniciando heartbeat...\n")
        
        try:
            while self.running:
                self.heartbeat += 1
                
                # Heartbeat a cada 30 segundos
                if self.heartbeat % 30 == 0:
                    log.info(f"💓 Heartbeat #{self.heartbeat} - {datetime.now().strftime('%H:%M:%S')}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            log.info("\n🛑 Bot parado")
    
    def stop(self):
        self.running = False
        log.info("\n🛑 Bot finalizado")

# ============= MAIN =============
if __name__ == "__main__":
    print("\n" + "🚀"*30)
    print(" INICIANDO BOT DE TESTE")
    print("🚀"*30 + "\n")
    
    bot = SimpleBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(f"❌ Erro: {e}")
        bot.stop()
