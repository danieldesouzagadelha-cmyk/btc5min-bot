#!/usr/bin/env python3
"""
=================================================================
    BOT DE FARM 24/7 - POLYMARKET
    Estratégia: Prover liquidez e farmar rewards
    Roda 24 horas por dia, 7 dias por semana
    Lucro: Rewards + Rebates + Spread
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

load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # Modo de operação
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    
    # Capital (recomendado: $5.000 - $10.000 para farm)
    CAPITAL = float(os.getenv("CAPITAL", "1000.0"))  # Comece com $1000
    
    # Configurações de Market Making
    MM = {
        "max_positions": 5,              # Máx 5 pares simultâneos
        "position_size_pct": 0.02,        # 2% do capital por posição
        "target_spread_bps": 50,           # Spread alvo em basis points (0.5%)
        "min_spread_bps": 20,              # Spread mínimo (0.2%)
        "rebalance_interval": 60,           # Rebalancear a cada 60 segundos
        "inventory_target": 0.5,            # Target 50% UP / 50% DOWN
        "max_inventory_skew": 0.3           # Máx 80% de um lado
    }
    
    # Mercados alvo (foco em BTC 5min por enquanto)
    MARKETS = [
        "btc-updown-5m",  # Mercados de 5 minutos
    ]
    
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
    format="%(asctime)s [FARM] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("FarmBot")

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
    except Exception as e:
        log.debug(f"Erro Telegram: {e}")

# ============= CLIENTE POLYMARKET =============
class PolymarketClient:
    def __init__(self):
        self.gamma_url = config.GAMMA_URL
        self.clob_url = config.CLOB_URL
        self.session = requests.Session()
        
    def get_active_markets(self, tag="btc-updown-5m"):
        """Busca mercados ativos"""
        try:
            url = f"{self.gamma_url}/markets"
            params = {
                "tag_slug": tag,
                "active": "true",
                "limit": 50
            }
            resp = self.session.get(url, params=params, timeout=5)
            return resp.json() if resp.status_code == 200 else []
        except:
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
    
    def get_fair_price(self, market_id):
        """Calcula preço justo (médio entre bid/ask)"""
        book = self.get_order_book(market_id)
        if not book["bids"] or not book["asks"]:
            return 0.5
        
        best_bid = float(book["bids"][0]["price"])
        best_ask = float(book["asks"][0]["price"])
        return (best_bid + best_ask) / 2
    
    def place_limit_order(self, market_id, side, price, size):
        """Coloca ordem limitada (maker)"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] {side} {size:.2f} @ ${price:.3f}")
            return {"success": True, "order_id": f"sim_{int(time.time())}"}
        
        # TODO: Implementar ordem real com py-clob-client
        log.warning("Modo real não implementado - simulando")
        return {"success": True, "order_id": f"mock_{int(time.time())}"}
    
    def cancel_order(self, order_id):
        """Cancela uma ordem"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] Cancelando {order_id}")
            return True
        return True

# ============= GERENCIADOR DE POSIÇÕES =============
class PositionManager:
    def __init__(self):
        self.positions = []  # Pares de posições (UP + DOWN)
        self.total_capital = config.CAPITAL
        self.used_capital = 0
        self.daily_pnl = 0
        self.total_pnl = 0
        self.rewards_collected = 0
        self.rebates_collected = 0
        self.start_time = time.time()
        
    def can_open_position(self):
        """Verifica se pode abrir nova posição"""
        return (len(self.positions) < config.MM["max_positions"] and 
                self.used_capital < self.total_capital * 0.8)
    
    def calculate_position_size(self):
        """Calcula tamanho da posição"""
        available = self.total_capital - self.used_capital
        return min(available * config.MM["position_size_pct"],
                  self.total_capital * 0.1)  # Max 10% por posição
    
    def open_position(self, market_id, up_price, down_price, spread):
        """Abre um par de ordens (compra UP e vende DOWN)"""
        if not self.can_open_position():
            return None
        
        size = self.calculate_position_size()
        
        # Calcula preços com spread
        mid = (up_price + down_price) / 2
        half_spread = spread / 2
        
        bid_up = mid - half_spread
        ask_up = mid + half_spread
        bid_down = 1 - ask_up
        ask_down = 1 - bid_up
        
        position = {
            "market_id": market_id,
            "entry_time": time.time(),
            "size": size,
            "up_orders": {
                "bid": {"price": bid_up, "size": size, "status": "open"},
                "ask": {"price": ask_up, "size": size, "status": "open"}
            },
            "down_orders": {
                "bid": {"price": bid_down, "size": size, "status": "open"},
                "ask": {"price": ask_down, "size": size, "status": "open"}
            },
            "up_filled": 0,
            "down_filled": 0,
            "up_pnl": 0,
            "down_pnl": 0
        }
        
        self.positions.append(position)
        self.used_capital += size * 2  # Prende capital dos dois lados
        
        log.info(f"\n📊 NOVA POSIÇÃO - Mercado: {market_id[:8]}...")
        log.info(f"   UP: Bid ${bid_up:.3f} | Ask ${ask_up:.3f}")
        log.info(f"   DOWN: Bid ${bid_down:.3f} | Ask ${ask_down:.3f}")
        log.info(f"   Spread: {spread*100:.2f}% | Tamanho: ${size:.2f}")
        
        return position
    
    def update_position(self, position, side, order_type, filled_price):
        """Atualiza posição quando uma ordem executa"""
        if side == "UP":
            if order_type == "bid":
                position["up_filled"] += position["size"]
                position["up_pnl"] += (1 - filled_price) * position["size"]
                position["up_orders"]["bid"]["status"] = "filled"
            else:  # ask
                position["up_filled"] -= position["size"]
                position["up_pnl"] += (filled_price) * position["size"]
                position["up_orders"]["ask"]["status"] = "filled"
        else:  # DOWN
            if order_type == "bid":
                position["down_filled"] += position["size"]
                position["down_pnl"] += (1 - filled_price) * position["size"]
                position["down_orders"]["bid"]["status"] = "filled"
            else:  # ask
                position["down_filled"] -= position["size"]
                position["down_pnl"] += (filled_price) * position["size"]
                position["down_orders"]["ask"]["status"] = "filled"
        
        # Se ambos os lados executaram, lucro garantido!
        if (position["up_filled"] > 0 and position["down_filled"] < 0) or \
           (position["up_filled"] < 0 and position["down_filled"] > 0):
            total_pnl = position["up_pnl"] + position["down_pnl"]
            log.info(f"✅ POSIÇÃO FECHOU COM LUCRO: ${total_pnl:.2f}")
            self.total_pnl += total_pnl
            self.daily_pnl += total_pnl
            self.used_capital -= position["size"] * 2
            self.positions.remove(position)
    
    def check_inventory_skew(self):
        """Verifica se o inventário está muito desbalanceado"""
        for position in self.positions[:]:
            up_exposure = position["up_filled"]
            down_exposure = position["down_filled"]
            
            if abs(up_exposure - down_exposure) > config.MM["max_inventory_skew"]:
                log.warning(f"⚠️ Inventário desbalanceado - Rebalanceando")
                # TODO: Rebalancear ajustando preços
                self.positions.remove(position)
                self.used_capital -= position["size"] * 2
    
    def get_stats(self):
        """Retorna estatísticas"""
        elapsed = time.time() - self.start_time
        hours = elapsed / 3600
        
        return {
            "uptime": f"{hours:.1f}h",
            "capital": self.total_capital,
            "used": self.used_capital,
            "free": self.total_capital - self.used_capital,
            "positions": len(self.positions),
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "rewards": self.rewards_collected,
            "rebates": self.rebates_collected,
            "total_earned": self.total_pnl + self.rewards_collected + self.rebates_collected
        }
    
    def print_stats(self):
        """Mostra estatísticas"""
        s = self.get_stats()
        
        log.info("\n" + "="*60)
        log.info("📊 ESTATÍSTICAS DO FARM")
        log.info("="*60)
        log.info(f"⏱️  Uptime: {s['uptime']}")
        log.info(f"💰 Capital: ${s['capital']:.2f}")
        log.info(f"📊 Em uso: ${s['used']:.2f} | Livre: ${s['free']:.2f}")
        log.info(f"📈 Posições: {s['positions']}")
        log.info("-"*40)
        log.info(f"💵 PnL Hoje: ${s['daily_pnl']:.2f}")
        log.info(f"💵 PnL Total: ${s['total_pnl']:.2f}")
        log.info(f"🎁 Rewards: ${s['rewards']:.2f}")
        log.info(f"💰 Rebates: ${s['rebates']:.2f}")
        log.info(f"✨ TOTAL GANHO: ${s['total_earned']:.2f}")
        log.info("="*60)

# ============= ESTRATÉGIA DE SPREAD =============
class SpreadStrategy:
    def __init__(self):
        self.last_rebalance = 0
    
    def calculate_spread(self, market_id, client):
        """Calcula spread ideal baseado na liquidez"""
        book = client.get_order_book(market_id)
        
        if not book["bids"] or not book["asks"]:
            return config.MM["target_spread_bps"] / 10000
        
        best_bid = float(book["bids"][0]["price"])
        best_ask = float(book["asks"][0]["price"])
        current_spread = best_ask - best_bid
        
        # Ajusta spread baseado na liquidez atual
        if current_spread < 0.001:  # Muito líquido
            return config.MM["min_spread_bps"] / 10000
        elif current_spread > 0.01:  # Pouco líquido
            return config.MM["target_spread_bps"] / 10000 * 1.5
        else:
            return config.MM["target_spread_bps"] / 10000
    
    def should_rebalance(self):
        """Verifica se já pode rebalancear"""
        return time.time() - self.last_rebalance > config.MM["rebalance_interval"]

# ============= COLETOR DE REWARDS =============
class RewardCollector:
    def __init__(self, positions):
        self.positions = positions
        self.last_check = time.time()
        self.daily_rewards = 0
        
    def check_rewards(self):
        """Verifica e coleta recompensas (simulado)"""
        now = time.time()
        
        # A cada hora, simula coleta de rewards
        if now - self.last_check > 3600:
            # Simula rewards baseado no capital em uso
            capital_used = self.positions.used_capital
            hourly_reward = capital_used * 0.00001  # ~0.72% ao mês
            
            self.positions.rewards_collected += hourly_reward
            self.daily_rewards += hourly_reward
            self.last_check = now
            
            log.info(f"🎁 Rewards coletados: ${hourly_reward:.2f}")
            
            # Reseta daily rewards à meia-noite
            if datetime.now().hour == 0 and datetime.now().minute < 5:
                log.info(f"📊 Rewards de hoje: ${self.daily_rewards:.2f}")
                self.daily_rewards = 0

# ============= BOT PRINCIPAL =============
class FarmBot:
    def __init__(self):
        self.client = PolymarketClient()
        self.positions = PositionManager()
        self.strategy = SpreadStrategy()
        self.rewards = RewardCollector(self.positions)
        
        self.running = True
        self.markets_cache = {}
        self.cycle = 0
        
        log.info("\n" + "🌾"*60)
        log.info(" FARM BOT 24/7 - POLYMARKET")
        log.info("🌾"*60)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Capital: ${config.CAPITAL}")
        log.info(f" Estratégia: Market Making + Liquidity Rewards")
        log.info("🌾"*60)
        
        send_telegram(
            f"<b>🌾 FARM BOT INICIADO</b>\n\n"
            f"Capital: ${config.CAPITAL}\n"
            f"Farmando rewards 24/7\n"
            f"Spread alvo: {config.MM['target_spread_bps']/100}%"
        )
    
    def scan_markets(self):
        """Escaneia mercados por oportunidades"""
        all_markets = []
        
        for tag in config.MARKETS:
            markets = self.client.get_active_markets(tag)
            all_markets.extend(markets)
            time.sleep(0.5)  # Rate limiting
        
        log.info(f"\n🔍 Mercados ativos: {len(all_markets)}")
        return all_markets
    
    def manage_positions(self):
        """Gerencia posições existentes"""
        # Atualiza posições
        for position in self.positions.positions[:]:
            # Simula execução de ordens (20% de chance)
            if random.random() < 0.001:  # Muito raro para simulação
                side = random.choice(["UP", "DOWN"])
                order_type = random.choice(["bid", "ask"])
                price = position[f"{side.lower()}_orders"][order_type]["price"]
                self.positions.update_position(position, side, order_type, price)
        
        # Verifica desbalanceamento
        self.positions.check_inventory_skew()
    
    def open_new_positions(self):
        """Abre novas posições em mercados promissores"""
        if not self.positions.can_open_position():
            return
        
        markets = self.scan_markets()
        
        for market in markets[:5]:  # Limita a 5 por ciclo
            market_id = market.get("id", "")
            if not market_id:
                continue
            
            # Calcula preço justo
            fair_price = self.client.get_fair_price(market_id)
            
            # Calcula spread ideal
            spread = self.strategy.calculate_spread(market_id, self.client)
            
            # Abre posição
            self.positions.open_position(
                market_id=market_id,
                up_price=fair_price,
                down_price=1 - fair_price,
                spread=spread
            )
            
            time.sleep(1)  # Pausa entre aberturas
    
    def rebalance_if_needed(self):
        """Rebalanceia posições se necessário"""
        if self.strategy.should_rebalance():
            log.info("🔄 Rebalanceando posições...")
            
            for position in self.positions.positions[:]:
                # Atualiza preços baseado no mercado atual
                fair_price = self.client.get_fair_price(position["market_id"])
                spread = self.strategy.calculate_spread(position["market_id"], self.client)
                
                half_spread = spread / 2
                new_bid_up = fair_price - half_spread
                new_ask_up = fair_price + half_spread
                
                # Log das mudanças
                log.info(f"   {position['market_id'][:8]}... "
                        f"UP: ${new_bid_up:.3f}/${new_ask_up:.3f}")
            
            self.strategy.last_rebalance = time.time()
    
    def run(self):
        """Loop principal"""
        log.info("\n🚀 FARM BOT RODANDO 24/7\n")
        
        try:
            while self.running:
                self.cycle += 1
                
                # 1. Gerencia posições existentes
                self.manage_positions()
                
                # 2. Abre novas posições
                if self.cycle % 10 == 0:  # A cada ~10 segundos
                    self.open_new_positions()
                
                # 3. Rebalanceia
                self.rebalance_if_needed()
                
                # 4. Coleta rewards
                self.rewards.check_rewards()
                
                # 5. Mostra status a cada 5 minutos
                if self.cycle % 300 == 0:
                    self.positions.print_stats()
                
                # 6. Heartbeat a cada minuto
                if self.cycle % 60 == 0:
                    log.info(f"💓 Heartbeat - Posições: {len(self.positions.positions)}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            log.error(f"❌ Erro fatal: {e}")
            self.stop()
    
    def stop(self):
        """Parada graceful"""
        self.running = False
        log.info("\n🛑 Farm Bot parado")
        self.positions.print_stats()
        
        send_telegram(
            f"<b>🛑 FARM BOT PARADO</b>\n\n"
            f"Total ganho: ${self.positions.get_stats()['total_earned']:.2f}"
        )

# ============= MAIN =============
if __name__ == "__main__":
    print("\n" + "🌾"*30)
    print(" FARM BOT 24/7 - POLYMARKET")
    print("🌾"*30 + "\n")
    print(" RODANDO 24 HORAS POR DIA")
    print(" Farmando Rewards + Rebates + Spread\n")
    
    bot = FarmBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(f"❌ Erro: {e}")
        bot.stop()
