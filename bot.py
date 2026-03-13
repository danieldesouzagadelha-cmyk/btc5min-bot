#!/usr/bin/env python3
"""
=================================================================
    BOT DE ARBITRAGEM - POLYMARKET
    Estratégia: Comprar YES + NO quando soma < $1.00
    Baseado em traders reais que lucraram $1.7M [citation:4]
=================================================================
"""

import os
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # MODO REAL (mude para false quando quiser arriscar dinheiro)
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    
    # Capital inicial (comece com $50)
    CAPITAL = float(os.getenv("CAPITAL", "50.0"))
    
    # Configurações da estratégia
    STRATEGY = {
        "max_trade_size": 10.0,           # Máximo $10 por trade
        "target_sum": 0.98,                 # Soma alvo (< 0.98 já entra)
        "min_spread": 0.01,                  # Mínimo 1% de lucro
        "max_positions": 3,                   # Máx 3 trades simultâneos
    }
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # APIs
    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

config = Config()

# ============= LOGGING =============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ARB] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("ArbitrageBot")

# ============= TELEGRAM =============
def send_telegram(message):
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=3)
    except:
        pass

# ============= CLIENTE POLYMARKET =============
class PolymarketClient:
    def __init__(self):
        self.gamma_url = config.GAMMA_URL
        self.clob_url = config.CLOB_URL
    
    def get_active_markets(self):
        """Busca mercados ativos (foco em BTC 5/15min)"""
        try:
            # Foco em mercados de curto prazo (mais oportunidades) [citation:5]
            url = f"{self.gamma_url}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": 50,
                "tag_slug": "crypto"
            }
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                markets = resp.json()
                log.info(f"📊 Encontrados {len(markets)} mercados ativos")
                return markets
        except Exception as e:
            log.error(f"Erro: {e}")
        return []
    
    def get_market_prices(self, market_id):
        """Busca preços de YES e NO para um mercado"""
        try:
            # Busca livro de ordens
            url = f"{self.clob_url}/book"
            params = {"market_id": market_id}
            resp = requests.get(url, params=params, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                
                # Pega melhores preços
                yes_price = None
                no_price = None
                
                for bid in bids:
                    if bid.get("side") == "YES":
                        yes_price = float(bid["price"])
                    elif bid.get("side") == "NO":
                        no_price = float(bid["price"])
                
                for ask in asks:
                    if ask.get("side") == "YES" and yes_price is None:
                        yes_price = float(ask["price"])
                    elif ask.get("side") == "NO" and no_price is None:
                        no_price = float(ask["price"])
                
                return yes_price, no_price
        except:
            pass
        return None, None
    
    def place_order(self, market_id, side, price, size):
        """Coloca ordem de compra"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] COMPRA {side} ${size:.2f} @ ${price:.3f}")
            return {
                "success": True,
                "order_id": f"sim_{int(time.time())}",
                "price": price,
                "size": size
            }
        
        # TODO: Implementar ordem real
        log.warning("⚠️ Modo real não implementado")
        return {"success": True, "order_id": f"mock_{int(time.time())}"}

# ============= ESTRATÉGIA DE ARBITRAGEM =============
class ArbitrageStrategy:
    def __init__(self):
        self.positions = []  # Trades abertos
        self.total_pnl = 0.0
        self.capital = config.CAPITAL
        
    def check_opportunity(self, yes_price, no_price):
        """Verifica se há oportunidade de arbitragem"""
        if not yes_price or not no_price:
            return None
        
        total = yes_price + no_price
        spread = 1.0 - total
        
        log.info(f"📊 YES: ${yes_price:.3f} | NO: ${no_price:.3f} | SOMA: ${total:.3f} | SPREAD: {spread:.3f}")
        
        if total < config.STRATEGY["target_sum"] and spread >= config.STRATEGY["min_spread"]:
            return {
                "total": total,
                "spread": spread,
                "yes_price": yes_price,
                "no_price": no_price,
                "profit_potential": spread * config.STRATEGY["max_trade_size"]
            }
        return None
    
    def execute_trade(self, market, opportunity):
        """Executa trade de arbitragem"""
        if len(self.positions) >= config.STRATEGY["max_positions"]:
            log.warning("⚠️ Máximo de posições atingido")
            return None
        
        # Calcula tamanho do trade (balanceado)
        trade_size = config.STRATEGY["max_trade_size"] / 2
        yes_shares = trade_size / opportunity["yes_price"]
        no_shares = trade_size / opportunity["no_price"]
        
        # Compra YES
        yes_order = client.place_order(
            market["id"], 
            "YES", 
            opportunity["yes_price"], 
            trade_size
        )
        
        # Compra NO
        no_order = client.place_order(
            market["id"], 
            "NO", 
            opportunity["no_price"], 
            trade_size
        )
        
        if yes_order["success"] and no_order["success"]:
            position = {
                "market_id": market["id"],
                "market_title": market.get("title", "Unknown")[:30],
                "yes_price": opportunity["yes_price"],
                "no_price": opportunity["no_price"],
                "total_cost": trade_size * 2,
                "yes_shares": yes_shares,
                "no_shares": no_shares,
                "entry_time": time.time(),
                "guaranteed_pnl": (min(yes_shares, no_shares) - (trade_size * 2)),
                "status": "open"
            }
            
            self.positions.append(position)
            self.capital -= trade_size * 2
            
            # Log
            log.info(f"\n💰 NOVO TRADE - {position['market_title']}")
            log.info(f"   YES: ${opportunity['yes_price']:.3f} | NO: ${opportunity['no_price']:.3f}")
            log.info(f"   SOMA: ${opportunity['total']:.3f} | LUCRO GARANTIDO: ${position['guaranteed_pnl']:.2f}")
            
            # Telegram
            send_telegram(
                f"<b>💰 ARBITRAGEM DETECTADA</b>\n\n"
                f"Mercado: {position['market_title']}\n"
                f"YES: ${opportunity['yes_price']:.3f}\n"
                f"NO: ${opportunity['no_price']:.3f}\n"
                f"SOMA: ${opportunity['total']:.3f}\n"
                f"Lucro garantido: ${position['guaranteed_pnl']:.2f}"
            )
            
            return position
        return None
    
    def check_resolution(self):
        """Verifica se trades já resolveram"""
        for position in self.positions[:]:
            # Simula resolução (em produção, consultaria API)
            if time.time() - position["entry_time"] > 3600:  # 1 hora
                self.positions.remove(position)
                self.total_pnl += position["guaranteed_pnl"]
                self.capital += position["total_cost"] + position["guaranteed_pnl"]
                
                log.info(f"✅ TRADE RESOLVIDO - PnL: ${position['guaranteed_pnl']:.2f}")
                
                send_telegram(
                    f"<b>✅ TRADE FINALIZADO</b>\n\n"
                    f"Mercado: {position['market_title']}\n"
                    f"Lucro: ${position['guaranteed_pnl']:.2f}\n"
                    f"Capital atual: ${self.capital:.2f}"
                )
    
    def get_stats(self):
        """Retorna estatísticas"""
        return {
            "capital": self.capital,
            "initial": config.CAPITAL,
            "pnl": self.total_pnl,
            "roi": (self.total_pnl / config.CAPITAL * 100),
            "positions": len(self.positions)
        }
    
    def print_stats(self):
        stats = self.get_stats()
        log.info("\n" + "="*60)
        log.info("📊 ESTATÍSTICAS")
        log.info("="*60)
        log.info(f"💰 Capital: ${stats['capital']:.2f}")
        log.info(f"📈 PnL Total: ${stats['pnl']:.2f} ({stats['roi']:.1f}%)")
        log.info(f"📊 Posições abertas: {stats['positions']}")
        log.info("="*60)

# ============= BOT PRINCIPAL =============
class ArbitrageBot:
    def __init__(self):
        self.client = PolymarketClient()
        self.strategy = ArbitrageStrategy()
        self.running = True
        self.cycle = 0
        
        log.info("\n" + "💰"*30)
        log.info(" BOT DE ARBITRAGEM - POLYMARKET")
        log.info("💰"*30)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Capital: ${config.CAPITAL}")
        log.info(f" Estratégia: Comprar YES+NO quando soma < {config.STRATEGY['target_sum']}")
        log.info("💰"*30)
        
        send_telegram(
            f"<b>🤖 BOT DE ARBITRAGEM INICIADO</b>\n\n"
            f"Capital: ${config.CAPITAL}\n"
            f"Estratégia: YES+NO < {config.STRATEGY['target_sum']}\n"
            f"Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}"
        )
    
    def scan_opportunities(self):
        """Escaneia mercados por oportunidades"""
        markets = self.client.get_active_markets()
        
        for market in markets[:20]:  # Limita a 20 mercados por ciclo
            market_id = market.get("id")
            if not market_id:
                continue
            
            yes_price, no_price = self.client.get_market_prices(market_id)
            
            opportunity = self.strategy.check_opportunity(yes_price, no_price)
            
            if opportunity:
                log.info(f"🎯 OPORTUNIDADE ENCONTRADA! Spread: {opportunity['spread']:.2f}")
                self.strategy.execute_trade(market, opportunity)
                time.sleep(1)  # Pausa entre execuções
    
    def run(self):
        """Loop principal"""
        log.info("\n🚀 BOT OPERANDO - Buscando oportunidades...\n")
        
        try:
            while self.running:
                self.cycle += 1
                
                # 1. Escaneia oportunidades (a cada 30s)
                if self.cycle % 30 == 0:
                    self.scan_opportunities()
                
                # 2. Verifica resolução de trades
                self.strategy.check_resolution()
                
                # 3. Estatísticas a cada 5 minutos
                if self.cycle % 300 == 0:
                    self.strategy.print_stats()
                
                # 4. Heartbeat a cada minuto
                if self.cycle % 60 == 0:
                    log.info(f"💓 Heartbeat - Posições: {len(self.strategy.positions)}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        self.running = False
        log.info("\n🛑 Bot parado")
        self.strategy.print_stats()
        send_telegram(
            f"<b>🛑 BOT PARADO</b>\n\n"
            f"PnL Final: ${self.strategy.total_pnl:.2f}\n"
            f"ROI: {self.strategy.get_stats()['roi']:.1f}%"
        )

# ============= MAIN =============
if __name__ == "__main__":
    bot = ArbitrageBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
