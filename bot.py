#!/usr/bin/env python3
"""
=================================================================
    FARM BOT LP v1.0 - POLYMARKET
    Estratégia: Prover liquidez e farmar rewards
    Foco em segurança e consistência
    Potencial: Rewards + Rebates + Spread + Airdrop
=================================================================
"""

import os
import time
import json
import logging
import requests
import random
import threading
import hmac
import hashlib
from datetime import datetime, timedelta
from collections import deque
from dotenv import load_dotenv

load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # MODO REAL (mude para False quando quiser testar com dinheiro real)
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    
    # Capital inicial (comece com $50 para testar)
    CAPITAL = float(os.getenv("CAPITAL", "50.0"))
    
    # Configurações de Market Making (LP)
    LP = {
        "max_positions": 3,                 # Máx 3 pares (comece com 1-2)
        "position_size_pct": 0.10,           # 10% do capital por posição
        "target_spread_bps": 100,             # Spread alvo 1.0% (100 bps)
        "min_spread_bps": 50,                 # Spread mínimo 0.5%
        "rebalance_interval": 300,             # Rebalancear a cada 5 minutos
        "inventory_target": 0.5,               # Target 50% YES / 50% NO
        "max_inventory_skew": 0.30,             # Máx 65% de um lado (0.5 ± 0.15)
        "order_lifetime": 3600,                 # Cancelar ordens após 1 hora
        "min_volume_required": 1000,             # Volume mínimo diário
        "min_reward_score": 1.0                   # Score mínimo de recompensa
    }
    
    # Telegram para alertas
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # APIs
    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    # Carteira (NUNCA coloque a chave aqui! Use variáveis de ambiente)
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")

config = Config()

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
        self.session.headers.update({
            "User-Agent": "LiquidityBot/1.0"
        })
    
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
    
    def get_market_details(self, market_id):
        """Busca detalhes completos de um mercado"""
        try:
            url = f"{self.gamma_url}/markets/{market_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return None
    
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
    
    def calculate_lp_score(self, market):
        """Calcula score para decidir qual mercado farmar"""
        try:
            reward = float(market.get("liquidity_rewards", 0))
            volume = float(market.get("volume_24h", 0))
            spread = self.get_mid_price(market.get("id", ""))
            
            # Quanto maior reward e volume, melhor
            # Spread muito alto é ruim (menos trades)
            score = (reward * 1000) + (volume / 1000) - (spread * 100)
            
            return score
        except:
            return 0
    
    def place_limit_order(self, market_id, side, outcome, price, size):
        """Coloca ordem limitada (maker)"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] {side} {outcome} {size:.2f} @ ${price:.3f}")
            return {
                "success": True,
                "order_id": f"sim_{int(time.time())}_{random.randint(1000,9999)}",
                "price": price,
                "size": size
            }
        
        # TODO: Implementar com py-clob-client
        log.warning("⚠️ Modo real não implementado - simulando")
        return {
            "success": True,
            "order_id": f"mock_{int(time.time())}_{random.randint(1000,9999)}",
            "price": price,
            "size": size
        }
    
    def cancel_order(self, order_id):
        """Cancela uma ordem"""
        if config.SIMULATION_MODE:
            log.info(f"[SIM] Cancelando ordem {order_id[:8]}...")
            return True
        return True
    
    def get_balance(self):
        """Obtém saldo da carteira"""
        if config.SIMULATION_MODE:
            return config.CAPITAL
        # TODO: Implementar com web3
        return config.CAPITAL

# ============= GERENCIADOR DE POSIÇÕES LP =============
class LPPositionManager:
    def __init__(self, client):
        self.client = client
        self.positions = []          # Posições ativas
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
        """Verifica se pode abrir nova posição"""
        return (len(self.positions) < config.LP["max_positions"] and 
                self.used_capital < self.total_capital * 0.8)
    
    def calculate_position_size(self):
        """Calcula tamanho da posição baseado no capital disponível"""
        available = self.total_capital - self.used_capital
        size = min(
            available * config.LP["position_size_pct"],
            self.total_capital * 0.25  # Max 25% do capital total
        )
        return max(size, 5.0)  # Mínimo $5
    
    def calculate_prices(self, mid_price, spread_bps):
        """Calcula preços de bid/ask com spread"""
        spread = spread_bps / 10000  # Converte bps para decimal
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
        """Abre uma nova posição LP em um mercado"""
        if not self.can_open_position():
            return None
        
        market_id = market.get("id")
        if not market_id:
            return None
        
        # Usa spread configurado ou calcula baseado na liquidez
        if spread_bps is None:
            spread_bps = config.LP["target_spread_bps"]
        
        # Calcula preço justo
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
            "filled": {
                "yes": 0,
                "no": 0,
                "yes_value": 0,
                "no_value": 0
            },
            "pnl": 0,
            "inventory_skew": 0
        }
        
        # Coloca as 4 ordens
        self._place_position_orders(position)
        
        self.positions.append(position)
        self.used_capital += size * 2  # Prende capital dos dois lados
        self.stats["orders_placed"] += 4
        
        log.info(f"\n📊 NOVA POSIÇÃO LP")
        log.info(f"   Mercado: {market_id[:8]}... | {position['market_title']}")
        log.info(f"   YES: Bid ${prices['bid_yes']:.3f} | Ask ${prices['ask_yes']:.3f}")
        log.info(f"   NO:  Bid ${prices['bid_no']:.3f} | Ask ${prices['ask_no']:.3f}")
        log.info(f"   Spread: {spread_bps/100:.2f}% | Tamanho: ${size:.2f}")
        log.info(f"   Capital usado: ${size*2:.2f}")
        
        return position
    
    def _place_position_orders(self, position):
        """Coloca as 4 ordens para uma posição"""
        m = position["market_id"]
        p = position["prices"]
        size = position["size"]
        
        # Ordem de compra YES
        order = self.client.place_limit_order(m, "buy", "YES", p["bid_yes"], size)
        if order["success"]:
            position["orders"]["bid_yes"] = {"id": order["order_id"], "status": "open"}
        
        # Ordem de venda YES
        order = self.client.place_limit_order(m, "sell", "YES", p["ask_yes"], size)
        if order["success"]:
            position["orders"]["ask_yes"] = {"id": order["order_id"], "status": "open"}
        
        # Ordem de compra NO
        order = self.client.place_limit_order(m, "buy", "NO", p["bid_no"], size)
        if order["success"]:
            position["orders"]["bid_no"] = {"id": order["order_id"], "status": "open"}
        
        # Ordem de venda NO
        order = self.client.place_limit_order(m, "sell", "NO", p["ask_no"], size)
        if order["success"]:
            position["orders"]["ask_no"] = {"id": order["order_id"], "status": "open"}
    
    def update_positions(self):
        """Atualiza todas as posições"""
        for position in self.positions[:]:
            self._update_single_position(position)
    
    def _update_single_position(self, position):
        """Atualiza uma posição específica"""
        # Simula execução de ordens (em modo real, consultaria a API)
        if config.SIMULATION_MODE and random.random() < 0.001:  # 0.1% chance
            self._simulate_order_execution(position)
        
        # Verifica tempo de vida das ordens
        if time.time() - position["entry_time"] > config.LP["order_lifetime"]:
            self._cancel_position_orders(position)
            self.positions.remove(position)
            self.used_capital -= position["size"] * 2
            log.info(f"⏰ Posição {position['market_id'][:8]} expirada - ordens canceladas")
        
        # Calcula skew do inventário
        yes_filled = position["filled"]["yes"]
        no_filled = position["filled"]["no"]
        total_filled = yes_filled + no_filled
        
        if total_filled > 0:
            yes_ratio = yes_filled / total_filled
            position["inventory_skew"] = abs(yes_ratio - 0.5)
            
            # Alerta se skew muito alto
            if position["inventory_skew"] > config.LP["max_inventory_skew"]:
                log.warning(f"⚠️ Skew alto em {position['market_id'][:8]}: {yes_ratio:.2f}")
                self._rebalance_position(position)
    
    def _simulate_order_execution(self, position):
        """Simula execução de ordens (apenas para teste)"""
        side = random.choice(["yes", "no"])
        order_type = random.choice(["bid", "ask"])
        
        if side == "yes":
            if order_type == "bid" and position["orders"]["bid_yes"]["status"] == "open":
                price = position["prices"]["bid_yes"]
                position["filled"]["yes"] += position["size"]
                position["filled"]["yes_value"] += position["size"] * price
                position["orders"]["bid_yes"]["status"] = "filled"
                self.stats["trades_executed"] += 1
                log.info(f"✅ Ordem executada: COMPRA YES @ ${price:.3f}")
                
        elif side == "no":
            if order_type == "bid" and position["orders"]["bid_no"]["status"] == "open":
                price = position["prices"]["bid_no"]
                position["filled"]["no"] += position["size"]
                position["filled"]["no_value"] += position["size"] * price
                position["orders"]["bid_no"]["status"] = "filled"
                self.stats["trades_executed"] += 1
                log.info(f"✅ Ordem executada: COMPRA NO @ ${price:.3f}")
    
    def _rebalance_position(self, position):
        """Rebalanceia uma posição desbalanceada"""
        # Cancela ordens existentes
        self._cancel_position_orders(position)
        
        # Ajusta preços para favorecer o lado oposto
        skew = position["inventory_skew"]
        mid_price = position["mid_price"]
        
        if position["filled"]["yes"] > position["filled"]["no"]:
            # Muito YES, ajusta para favorecer NO
            new_spread = position["spread_bps"] * (1 + skew)
            prices = self.calculate_prices(mid_price - 0.02, new_spread)
        else:
            # Muito NO, ajusta para favorecer YES
            new_spread = position["spread_bps"] * (1 + skew)
            prices = self.calculate_prices(mid_price + 0.02, new_spread)
        
        position["prices"] = prices
        position["last_update"] = time.time()
        
        # Recoloca ordens
        self._place_position_orders(position)
        log.info(f"🔄 Posição {position['market_id'][:8]} rebalanceada")
    
    def _cancel_position_orders(self, position):
        """Cancela todas as ordens de uma posição"""
        for order_key in ["bid_yes", "ask_yes", "bid_no", "ask_no"]:
            order = position["orders"][order_key]
            if order["id"] and order["status"] == "open":
                if self.client.cancel_order(order["id"]):
                    order["status"] = "cancelled"
                    self.stats["orders_cancelled"] += 1
    
    def collect_rewards(self):
        """Coleta recompensas de liquidez (simulado)"""
        if len(self.positions) == 0:
            return
        
        # Simula rewards baseado no capital em uso
        hourly_rate = 0.00005  # 0.005% por hora (~3.6% ao mês)
        hourly_reward = self.used_capital * hourly_rate
        
        self.stats["rewards_collected"] += hourly_reward
        self.stats["total_pnl"] += hourly_reward
        self.stats["daily_pnl"] += hourly_reward
        
        log.info(f"🎁 Rewards coletados: ${hourly_reward:.2f}")
    
    def check_daily_reset(self):
        """Reseta contadores diários"""
        today = datetime.now().date()
        if today != self.last_reset:
            log.info(f"📊 Resumo diário - PnL: ${self.stats['daily_pnl']:.2f}")
            self.stats["daily_pnl"] = 0
            self.last_reset = today
    
    def get_stats(self):
        """Retorna estatísticas completas"""
        elapsed = time.time() - self.stats["start_time"]
        hours = elapsed / 3600
        
        total_earned = (self.stats["total_pnl"] + 
                       self.stats["rewards_collected"] + 
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
        """Mostra estatísticas no console"""
        s = self.get_stats()
        
        log.info("\n" + "="*70)
        log.info("📊 ESTATÍSTICAS DO FARM LP")
        log.info("="*70)
        log.info(f"⏱️  Uptime: {s['uptime']}")
        log.info(f"💰 Capital: ${s['capital']:.2f}")
        log.info(f"📊 Em uso: ${s['used']:.2f} | Livre: ${s['free']:.2f}")
        log.info(f"📈 Posições: {s['positions']}")
        log.info(f"📊 ROI: {s['roi']:.2f}%")
        log.info("-"*40)
        log.info(f"💵 PnL Total: ${s['total_pnl']:.2f}")
        log.info(f"🎁 Rewards: ${s['rewards_collected']:.2f}")
        log.info(f"💰 Rebates: ${s['rebates_collected']:.2f}")
        log.info(f"📊 Trades: {s['trades_executed']}")
        log.info(f"📈 Ordens colocadas: {s['orders_placed']}")
        log.info(f"📉 Ordens canceladas: {s['orders_cancelled']}")
        log.info(f"✨ TOTAL GANHO: ${s['total_earned']:.2f}")
        log.info("="*70)
        
        # Alerta se ROI for negativo
        if s['total_pnl'] < -5:
            send_telegram(f"⚠️ Alerta: PnL negativo de ${s['total_pnl']:.2f}")

# ============= BOT PRINCIPAL =============
class LPFarmBot:
    def __init__(self):
        self.client = PolymarketClient()
        self.positions = LPPositionManager(self.client)
        
        self.running = True
        self.cycle = 0
        self.last_rebalance = 0
        self.last_rewards = 0
        self.last_stats = 0
        self.known_markets = {}
        
        log.info("\n" + "🌾"*70)
        log.info(" FARM BOT LP v1.0 - POLYMARKET")
        log.info("🌾"*70)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Capital: ${config.CAPITAL}")
        log.info(f" Estratégia: Liquidity Provision + Rewards")
        log.info(f" Spread alvo: {config.LP['target_spread_bps']/100:.1f}%")
        log.info("🌾"*70)
        
        send_telegram(
            f"<b>🌾 FARM BOT LP INICIADO</b>\n\n"
            f"Capital: ${config.CAPITAL}\n"
            f"Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}\n"
            f"Spread alvo: {config.LP['target_spread_bps']/100}%"
        )
    
    def scan_markets(self):
        """Escaneia mercados com melhores recompensas"""
        markets = self.client.get_markets_with_rewards(limit=30)
        
        # Calcula score para cada mercado
        scored_markets = []
        for market in markets:
            score = self.client.calculate_lp_score(market)
            if score >= config.LP["min_reward_score"]:
                scored_markets.append((score, market))
        
        # Ordena por score
        scored_markets.sort(reverse=True)
        
        log.info(f"\n🔍 Top mercados com rewards:")
        for i, (score, market) in enumerate(scored_markets[:5]):
            title = market.get("title", "Unknown")[:40]
            reward = market.get("liquidity_rewards", 0)
            log.info(f"   {i+1}. [{score:.0f}] {title} - Reward: {reward}")
        
        return [m for _, m in scored_markets]
    
    def manage_positions(self):
        """Gerencia posições existentes"""
        # Atualiza posições
        self.positions.update_positions()
        
        # Rebalanceamento periódico
        if time.time() - self.last_rebalance > config.LP["rebalance_interval"]:
            self.last_rebalance = time.time()
            # Não precisa rebalancear explicitamente, já é feito no update
    
    def open_new_positions(self):
        """Abre novas posições em mercados promissores"""
        if not self.positions.can_open_position():
            return
        
        markets = self.scan_markets()
        
        for market in markets:
            if not self.positions.can_open_position():
                break
            
            market_id = market.get("id")
            if not market_id or market_id in self.known_markets:
                continue
            
            # Abre posição
            position = self.positions.open_position(market)
            if position:
                self.known_markets[market_id] = True
                time.sleep(2)  # Pausa entre aberturas
    
    def collect_rewards_periodically(self):
        """Coleta recompensas periodicamente"""
        if time.time() - self.last_rewards > 3600:  # A cada hora
            self.positions.collect_rewards()
            self.last_rewards = time.time()
    
    def print_periodic_stats(self):
        """Mostra estatísticas periodicamente"""
        if time.time() - self.last_stats > 300:  # A cada 5 minutos
            self.positions.print_stats()
            self.last_stats = time.time()
    
    def run(self):
        """Loop principal"""
        log.info("\n🚀 FARM BOT RODANDO 24/7\n")
        
        try:
            while self.running:
                self.cycle += 1
                
                # 1. Gerencia posições existentes
                self.manage_positions()
                
                # 2. Abre novas posições (a cada 30 segundos)
                if self.cycle % 30 == 0:
                    self.open_new_positions()
                
                # 3. Coleta rewards
                self.collect_rewards_periodically()
                
                # 4. Mostra estatísticas
                self.print_periodic_stats()
                
                # 5. Verifica reset diário
                self.positions.check_daily_reset()
                
                # 6. Heartbeat a cada minuto
                if self.cycle % 60 == 0:
                    log.info(f"💓 Heartbeat - Posições: {len(self.positions.positions)}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            log.error(f"❌ Erro fatal: {e}")
            import traceback
            traceback.print_exc()
            self.stop()
    
    def stop(self):
        """Parada graceful"""
        self.running = False
        log.info("\n🛑 Farm Bot LP parado")
        
        # Cancela todas as ordens abertas
        for position in self.positions.positions:
            self.positions._cancel_position_orders(position)
        
        self.positions.print_stats()
        
        send_telegram(
            f"<b>🛑 FARM BOT LP PARADO</b>\n\n"
            f"Total ganho: ${self.positions.get_stats()['total_earned']:.2f}"
        )

# ============= MAIN =============
if __name__ == "__main__":
    print("\n" + "🌾"*35)
    print(" FARM BOT LP - POLYMARKET")
    print("🌾"*35 + "\n")
    print(" RODANDO 24 HORAS POR DIA")
    print(" Farmando Rewards + Rebates + Spread + Airdrop\n")
    
    bot = LPFarmBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(f"❌ Erro: {e}")
        bot.stop()

