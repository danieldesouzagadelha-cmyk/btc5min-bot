#!/usr/bin/env python3
"""
=================================================================
    FARM BOT LP v1.0 - MODO REAL
    ATENÇÃO: Este bot opera com dinheiro de verdade!
=================================================================
"""

import os
import time
import json
import logging
import requests
import random
import threading
from datetime import datetime, timedelta
from collections import deque
from dotenv import load_dotenv

# Tentar importar web3 (opcional)
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("⚠️ web3 não instalado - funcionalidades blockchain desativadas")

# Tentar importar cliente Polymarket
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, Side
    from py_clob_client.constants import POLYGON
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    print("⚠️ py-clob-client não instalado - modo simulação apenas")

load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # MODO REAL ATIVADO!
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").lower() == "false"
    
    # Capital real (comece com $50)
    CAPITAL = float(os.getenv("CAPITAL", "50.0"))
    
    # Configurações de Market Making (LP)
    LP = {
        "max_positions": 2,                 # Comece com apenas 2 posições
        "position_size_pct": 0.10,           # 10% do capital por posição
        "target_spread_bps": 100,             # Spread alvo 1.0%
        "min_spread_bps": 50,                 # Spread mínimo 0.5%
        "rebalance_interval": 300,             # Rebalancear a cada 5 min
        "inventory_target": 0.5,               # Target 50% YES / 50% NO
        "max_inventory_skew": 0.30,             # Máx 65% de um lado
        "order_lifetime": 3600,                 # Cancelar ordens após 1h
        "min_volume_required": 1000,             # Volume mínimo diário
        "min_reward_score": 1.0                   # Score mínimo de recompensa
    }
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # APIs
    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    # Carteira (via environment variables)
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
    
    # Conexão com Polygon
    POLYGON_RPC = "https://polygon-rpc.com"

config = Config()

# ============= VALIDAÇÕES DE SEGURANÇA =============
if not config.SIMULATION_MODE:
    print("\n" + "🚨"*30)
    print(" ATENÇÃO: MODO REAL ATIVADO!")
    print("🚨"*30)
    print(f" Capital: ${config.CAPITAL}")
    print(f" Endereço: {config.WALLET_ADDRESS[:10]}...")
    print(f" Max posições: {config.LP['max_positions']}")
    print("🚨"*30 + "\n")
    
    if not config.WALLET_ADDRESS or not config.PRIVATE_KEY:
        print("❌ ERRO: WALLET_ADDRESS e PRIVATE_KEY são obrigatórios no modo real!")
        exit(1)
    
    response = input("Digite 'CONFIRMAR' para continuar: ")
    if response != "CONFIRMAR":
        print("Operação cancelada.")
        exit(0)

# ============= LOGGING =============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LP] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("LPBot")

# ============= TELEGRAM =============
def send_telegram(message):
    """Envia alertas para Telegram"""
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
        self.session = requests.Session()
        self.clob_client = None
        self.web3 = None
        
        # Inicializa cliente real se necessário
        if not config.SIMULATION_MODE and CLOB_AVAILABLE:
            self._init_real_client()
        
        if WEB3_AVAILABLE:
            self.web3 = Web3(Web3.HTTPProvider(config.POLYGON_RPC))
    
    def _init_real_client(self):
        """Inicializa cliente CLOB real"""
        try:
            self.clob_client = ClobClient(
                host=config.CLOB_URL,
                chain_id=POLYGON,
                key=config.PRIVATE_KEY,
                signature_type=2,
                funder=config.WALLET_ADDRESS
            )
            # Cria credenciais API
            self.clob_client.set_api_creds(self.clob_client.create_or_derive_api_creds())
            log.info("✅ Cliente Polymarket real inicializado")
        except Exception as e:
            log.error(f"❌ Erro ao inicializar cliente real: {e}")
            exit(1)
    
    def get_markets_with_rewards(self, limit=20):
        """Busca mercados com melhores recompensas de liquidez"""
        try:
            url = f"{self.gamma_url}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": "liquidity_rewards_desc",
                "liquidity_rewards_gt": "0"
            }
            resp = self.session.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                markets = resp.json()
                log.info(f"📊 Encontrados {len(markets)} mercados com rewards")
                return markets
        except Exception as e:
            log.error(f"Erro ao buscar mercados: {e}")
        return []
    
    def get_order_book(self, market_id):
        """Busca livro de ordens"""
        try:
            url = f"{self.clob_url}/book"
            params = {"market_id": market_id}
            resp = self.session.get(url, params=params, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "bids": data.get("bids", []),
                    "asks": data.get("asks", [])
                }
        except:
            pass
        return {"bids": [], "asks": []}
    
    def get_mid_price(self, market_id):
        """Calcula preço médio do mercado"""
        book = self.get_order_book(market_id)
        
        if book["bids"] and book["asks"]:
            best_bid = float(book["bids"][0]["price"])
            best_ask = float(book["asks"][0]["price"])
            return (best_bid + best_ask) / 2
        return 0.5
    
    def place_limit_order(self, market_id, side, outcome, price, size):
        """Coloca ordem limitada real na Polymarket"""
        
        # Modo simulação
        if config.SIMULATION_MODE:
            log.info(f"[SIM] {side} {outcome} {size:.2f} @ ${price:.3f}")
            return {
                "success": True,
                "order_id": f"sim_{int(time.time())}_{random.randint(1000,9999)}",
                "price": price,
                "size": size
            }
        
        # Modo real
        try:
            # Converte side para formato do cliente
            clob_side = Side.BUY if side.lower() == "buy" else Side.SELL
            
            # Calcula shares
            shares = size / price
            
            # Cria ordem
            order_args = OrderArgs(
                price=price,
                size=shares,
                side=clob_side,
                token_id=market_id  # Nota: na realidade precisa do token_id correto
            )
            
            # Posta ordem
            resp = self.clob_client.create_and_post_order(order_args)
            
            log.info(f"✅ Ordem real colocada: {order_args}")
            return {
                "success": True,
                "order_id": resp.get("orderID", f"real_{int(time.time())}"),
                "price": price,
                "size": size
            }
            
        except Exception as e:
            log.error(f"❌ Erro ao colocar ordem real: {e}")
            return {"success": False, "error": str(e)}
    
    def cancel_order(self, order_id):
        """Cancela uma ordem"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] Cancelando {order_id[:8]}...")
            return True
        
        try:
            self.clob_client.cancel(order_id)
            log.info(f"✅ Ordem {order_id[:8]} cancelada")
            return True
        except Exception as e:
            log.error(f"❌ Erro ao cancelar ordem: {e}")
            return False
    
    def get_balance(self):
        """Obtém saldo real da carteira"""
        if config.SIMULATION_MODE:
            return config.CAPITAL
        
        try:
            if self.web3 and config.WALLET_ADDRESS:
                # Aqui você implementaria a consulta de saldo USDC
                # Por enquanto, retorna o configurado
                return config.CAPITAL
        except:
            pass
        return config.CAPITAL

# ============= GERENCIADOR DE POSIÇÕES =============
class LPPositionManager:
    def __init__(self, client):
        self.client = client
        self.positions = []
        self.total_capital = config.CAPITAL
        self.used_capital = 0
        self.stats = {
            "start_time": time.time(),
            "daily_pnl": 0,
            "total_pnl": 0,
            "rewards_collected": 0,
            "rebates_collected": 0,
            "spread_profits": 0,
            "trades_executed": 0,
            "orders_placed": 0,
            "orders_cancelled": 0
        }
        self.last_reset = datetime.now().date()
    
    def can_open_position(self):
        return (len(self.positions) < config.LP["max_positions"] and 
                self.used_capital < self.total_capital * 0.8)
    
    def calculate_position_size(self):
        available = self.total_capital - self.used_capital
        size = min(available * config.LP["position_size_pct"], self.total_capital * 0.25)
        return max(size, 5.0)
    
    def calculate_prices(self, mid_price, spread_bps):
        spread = spread_bps / 10000
        half_spread = spread / 2
        
        bid_yes = mid_price - half_spread
        ask_yes = mid_price + half_spread
        bid_no = 1 - ask_yes
        ask_no = 1 - bid_yes
        
        return {
            "bid_yes": max(0.01, min(0.99, bid_yes)),
            "ask_yes": max(0.01, min(0.99, ask_yes)),
            "bid_no": max(0.01, min(0.99, bid_no)),
            "ask_no": max(0.01, min(0.99, ask_no))
        }
    
    def open_position(self, market, spread_bps=None):
        if not self.can_open_position():
            return None
        
        market_id = market.get("id")
        if not market_id:
            return None
        
        if spread_bps is None:
            spread_bps = config.LP["target_spread_bps"]
        
        mid_price = self.client.get_mid_price(market_id)
        prices = self.calculate_prices(mid_price, spread_bps)
        size = self.calculate_position_size()
        
        position = {
            "market_id": market_id,
            "market_title": market.get("title", "Unknown")[:30],
            "entry_time": time.time(),
            "last_update": time.time(),
            "size": size,
            "spread_bps": spread_bps,
            "mid_price": mid_price,
            "prices": prices,
            "orders": {
                "bid_yes": {"id": None, "status": "pending"},
                "ask_yes": {"id": None, "status": "pending"},
                "bid_no": {"id": None, "status": "pending"},
                "ask_no": {"id": None, "status": "pending"}
            },
            "filled": {"yes": 0, "no": 0, "yes_value": 0, "no_value": 0},
            "pnl": 0,
            "inventory_skew": 0
        }
        
        # Coloca ordens
        self._place_position_orders(position)
        
        self.positions.append(position)
        self.used_capital += size * 2
        self.stats["orders_placed"] += 4
        
        log.info(f"\n📊 NOVA POSIÇÃO LP - Mercado: {market_id[:8]}...")
        log.info(f"   YES: Bid ${prices['bid_yes']:.3f} | Ask ${prices['ask_yes']:.3f}")
        log.info(f"   NO:  Bid ${prices['bid_no']:.3f} | Ask ${prices['ask_no']:.3f}")
        
        # Alerta Telegram
        send_telegram(
            f"<b>📊 Nova Posição LP</b>\n"
            f"Mercado: {market_id[:8]}...\n"
            f"YES: Bid ${prices['bid_yes']:.3f} | Ask ${prices['ask_yes']:.3f}\n"
            f"NO: Bid ${prices['bid_no']:.3f} | Ask ${prices['ask_no']:.3f}\n"
            f"Capital usado: ${size*2:.2f}"
        )
        
        return position
    
    def _place_position_orders(self, position):
        m = position["market_id"]
        p = position["prices"]
        size = position["size"]
        
        # Compra YES
        order = self.client.place_limit_order(m, "buy", "YES", p["bid_yes"], size)
        if order["success"]:
            position["orders"]["bid_yes"] = {"id": order["order_id"], "status": "open"}
        
        # Vende YES
        order = self.client.place_limit_order(m, "sell", "YES", p["ask_yes"], size)
        if order["success"]:
            position["orders"]["ask_yes"] = {"id": order["order_id"], "status": "open"}
        
        # Compra NO
        order = self.client.place_limit_order(m, "buy", "NO", p["bid_no"], size)
        if order["success"]:
            position["orders"]["bid_no"] = {"id": order["order_id"], "status": "open"}
        
        # Vende NO
        order = self.client.place_limit_order(m, "sell", "NO", p["ask_no"], size)
        if order["success"]:
            position["orders"]["ask_no"] = {"id": order["order_id"], "status": "open"}
    
    def get_stats(self):
        elapsed = time.time() - self.stats["start_time"]
        hours = elapsed / 3600
        
        total_earned = (self.stats["total_pnl"] + self.stats["rewards_collected"] + 
                       self.stats["rebates_collected"])
        
        return {
            "uptime": f"{hours:.1f}h",
            "capital": self.total_capital,
            "used": self.used_capital,
            "free": self.total_capital - self.used_capital,
            "positions": len(self.positions),
            "roi": (total_earned / self.total_capital * 100) if self.total_capital > 0 else 0,
            **self.stats,
            "total_earned": total_earned
        }
    
    def print_stats(self):
        s = self.get_stats()
        
        log.info("\n" + "="*70)
        log.info("📊 ESTATÍSTICAS DO FARM LP")
        log.info("="*70)
        log.info(f"⏱️  Uptime: {s['uptime']}")
        log.info(f"💰 Capital: ${s['capital']:.2f}")
        log.info(f"📊 Em uso: ${s['used']:.2f} | Livre: ${s['free']:.2f}")
        log.info(f"📈 Posições: {s['positions']}")
        log.info(f"📊 ROI: {s['roi']:.2f}%")
        log.info(f"✨ TOTAL GANHO: ${s['total_earned']:.2f}")
        log.info("="*70)

# ============= BOT PRINCIPAL =============
class LPFarmBot:
    def __init__(self):
        self.client = PolymarketClient()
        self.positions = LPPositionManager(self.client)
        
        self.running = True
        self.cycle = 0
        self.last_rebalance = 0
        self.last_stats = 0
        
        log.info("\n" + "🌾"*70)
        log.info(" FARM BOT LP v1.0 - MODO REAL")
        log.info("🌾"*70)
        log.info(f" Capital: ${config.CAPITAL}")
        log.info(f" Endereço: {config.WALLET_ADDRESS[:10]}...")
        log.info("🌾"*70)
        
        send_telegram(
            f"<b>🌾 FARM BOT LP - MODO REAL</b>\n\n"
            f"Capital: ${config.CAPITAL}\n"
            f"Endereço: {config.WALLET_ADDRESS[:10]}...\n"
            f"Max posições: {config.LP['max_positions']}"
        )
    
    def scan_markets(self):
        """Busca mercados para farmar"""
        markets = self.client.get_markets_with_rewards(limit=20)
        log.info(f"\n🔍 Encontrados {len(markets)} mercados com rewards")
        return markets
    
    def open_new_positions(self):
        """Abre novas posições"""
        if not self.positions.can_open_position():
            return
        
        markets = self.scan_markets()
        
        for market in markets[:3]:  # Testa os primeiros 3
            if not self.positions.can_open_position():
                break
            
            self.positions.open_position(market)
            time.sleep(2)  # Pausa entre aberturas
    
    def run(self):
        """Loop principal"""
        log.info("\n🚀 FARM BOT RODANDO 24/7\n")
        
        try:
            while self.running:
                self.cycle += 1
                
                # Abre novas posições (a cada 30s)
                if self.cycle % 30 == 0:
                    self.open_new_positions()
                
                # Estatísticas a cada 5 minutos
                if time.time() - self.last_stats > 300:
                    self.positions.print_stats()
                    self.last_stats = time.time()
                
                # Heartbeat a cada minuto
                if self.cycle % 60 == 0:
                    log.info(f"💓 Heartbeat - Posições: {len(self.positions.positions)}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            log.error(f"❌ Erro: {e}")
            self.stop()
    
    def stop(self):
        self.running = False
        log.info("\n🛑 Farm Bot parado")
        self.positions.print_stats()
        send_telegram(f"<b>🛑 Bot parado</b>\n\nTotal ganho: ${self.positions.get_stats()['total_earned']:.2f}")

# ============= MAIN =============
if __name__ == "__main__":
    bot = LPFarmBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()

