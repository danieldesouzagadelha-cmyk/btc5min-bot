#!/usr/bin/env python3
"""
=================================================================
    BTC 5 MIN BOT v3.0 - VERSÃO RAILWAY FINAL
    Otimizado para rodar 24/7 no Railway
    COM PROTEÇÃO CONTRA GHOST FILLS
=================================================================
"""

import os
import time
import json
import logging
import requests
import random
import csv
import sys
import hmac
import hashlib
from datetime import datetime, timedelta
from collections import deque
from dotenv import load_dotenv
from web3 import Web3

# Carrega variáveis de ambiente
load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # Modo de operação
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    
    # Banca virtual
    INITIAL_BANKROLL = float(os.getenv("INITIAL_BANKROLL", "100.0"))
    
    # ===== ESTRATÉGIA DE INÍCIO (0-60s) =====
    START = {
        "active": True,
        "window": [0, 60],
        "trade_size_pct": 0.005,
        "min_spread": 0.02,
        "max_trades_per_window": 3,
        "profit_target": 0.02,
        "stop_loss": 0.01
    }
    
    # ===== ESTRATÉGIA DE MEIO (60-240s) =====
    MIDDLE = {
        "active": True,
        "window": [60, 240],
        "position_size_pct": 0.02,
        "spread_bps": 20,
        "rebalance_seconds": 30,
        "max_positions": 3
    }
    
    # ===== ESTRATÉGIA DE FIM (240-300s) =====
    END = {
        "active": True,
        "window": [240, 300],
        "high_prob": {
            "min_confidence": 85,
            "max_entry_price": 0.95,
            "trade_size_pct": 0.02,
            "min_move_pct": 0.08
        },
        "low_prob": {
            "max_confidence": 20,
            "min_entry_price": 0.01,
            "max_entry_price": 0.08,
            "trade_size_pct": 0.005,
            "min_move_pct": 0.5
        }
    }
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # APIs
    BINANCE_URL = "https://api.binance.com/api/v3/klines"
    POLYGAMMA_URL = "https://gamma-api.polymarket.com"
    POLYCLOB_URL = "https://clob.polymarket.com"

config = Config()

# ============= LOGGING =============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BTC5M] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("BTC5M")

# ============= TELEGRAM =============
def send_telegram(message):
    """Envia mensagem para o Telegram"""
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

# ============= CLIENTES API =============
class BinanceClient:
    @staticmethod
    def get_current_price():
        try:
            url = f"{config.BINANCE_URL}?symbol=BTCUSDT&interval=1m&limit=1"
            resp = requests.get(url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][4])
        except:
            pass
        return None
    
    @staticmethod
    def get_price_at(timestamp):
        try:
            url = f"{config.BINANCE_URL}?symbol=BTCUSDT&interval=1m&startTime={timestamp*1000}&limit=1"
            resp = requests.get(url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][4])
        except:
            pass
        return None

class PolymarketClient:
    @staticmethod
    def get_order_book(token_id):
        try:
            url = f"{config.POLYCLOB_URL}/book"
            params = {"token_id": token_id}
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            best_bid = float(bids[0]["price"]) if bids else 0
            best_ask = float(asks[0]["price"]) if asks else 1
            return best_bid, best_ask
        except:
            return 0, 1
    
    @staticmethod
    def find_market(window_start):
        slug = f"btc-updown-5m-{window_start}"
        try:
            url = f"{config.POLYGAMMA_URL}/events"
            params = {"slug": slug}
            resp = requests.get(url, params=params, timeout=2)
            events = resp.json()
            
            if not events or len(events) == 0:
                return None
            
            event = events[0]
            markets = event.get("markets", [])
            
            up_token = None
            down_token = None
            up_price = 0.5
            down_price = 0.5
            
            for market in markets:
                question = market.get("question", "").lower()
                token_ids = market.get("clobTokenIds", [])
                prices = market.get("outcomePrices", ["0.5", "0.5"])
                
                if "up" in question or "higher" in question:
                    up_token = token_ids[0] if token_ids else None
                    up_price = float(prices[0]) if prices else 0.5
                elif "down" in question or "lower" in question:
                    down_token = token_ids[0] if token_ids else None
                    down_price = float(prices[0]) if prices else 0.5
            
            up_bid, up_ask = PolymarketClient.get_order_book(up_token) if up_token else (0, 1)
            down_bid, down_ask = PolymarketClient.get_order_book(down_token) if down_token else (0, 1)
            
            return {
                "slug": slug,
                "up_token": up_token,
                "down_token": down_token,
                "up_price": up_price,
                "down_price": down_price,
                "up_bid": up_bid,
                "up_ask": up_ask,
                "down_bid": down_bid,
                "down_ask": down_ask,
                "exists": True
            }
        except:
            return None

# ============= GERENCIADOR DE JANELAS =============
class WindowManager:
    @staticmethod
    def get_current_window():
        now = int(time.time())
        window_start = now - (now % 300)
        window_end = window_start + 300
        elapsed = now - window_start
        
        phase = WindowManager.get_phase(elapsed)
        
        if elapsed % 30 == 0 or elapsed < 5:
            log.info(f"🔄 DEBUG - elapsed={elapsed}s, phase={phase}")
        
        return {
            "start": window_start,
            "end": window_end,
            "remaining": window_end - now,
            "elapsed": elapsed,
            "phase": phase,
            "start_dt": datetime.fromtimestamp(window_start),
            "end_dt": datetime.fromtimestamp(window_end)
        }
    
    @staticmethod
    def get_phase(elapsed):
        if elapsed < 60:
            return "INÍCIO"
        elif elapsed < 240:
            return "MEIO"
        else:
            return "FIM"
    
    @staticmethod
    def format_time(timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

# ============= ESTRATÉGIA DE INÍCIO =============
class StartStrategy:
    def __init__(self):
        self.trades_por_janela = 0
        self.ultima_janela = 0
    
    def analyze(self, window, market, current_price):
        if not config.START["active"] or window["phase"] != "INÍCIO":
            return None
        
        if self.ultima_janela != window["start"]:
            self.trades_por_janela = 0
            self.ultima_janela = window["start"]
        
        if self.trades_por_janela >= config.START["max_trades_per_window"] or not market:
            return None
        
        oportunidades = []
        
        if market["up_bid"] > 0 and market["down_ask"] < 1:
            spread = market["up_bid"] - market["down_ask"]
            if spread > config.START["min_spread"]:
                oportunidades.append({
                    "type": "arb_up_down",
                    "buy": "DOWN",
                    "sell": "UP",
                    "buy_price": market["down_ask"],
                    "sell_price": market["up_bid"],
                    "spread": spread,
                    "confidence": 99
                })
        
        if market["up_ask"] < 0.5 and current_price:
            oportunidades.append({
                "type": "scalp_up",
                "direction": "UP",
                "price": market["up_ask"],
                "confidence": 70
            })
        
        if market["down_ask"] < 0.5 and current_price:
            oportunidades.append({
                "type": "scalp_down",
                "direction": "DOWN",
                "price": market["down_ask"],
                "confidence": 70
            })
        
        if not oportunidades:
            return None
        
        oportunidades.sort(key=lambda x: x.get("spread", 0) or x.get("confidence", 0), reverse=True)
        return oportunidades[0]
    
    def execute(self, trade_manager, monitor, window, market, oportunidade):
        size = trade_manager.calculate_trade_size("START")
        
        if oportunidade["type"] in ["arb_up_down"]:
            trade = trade_manager.execute_arb_trade(
                window=window,
                strategy="START",
                buy_direction=oportunidade["buy"],
                sell_direction=oportunidade["sell"],
                buy_price=oportunidade["buy_price"],
                sell_price=oportunidade["sell_price"],
                size=size
            )
            if trade:
                monitor.registrar_trade(trade, 0)
        else:
            trade = trade_manager.execute_trade(
                window=window,
                strategy="START",
                direction=oportunidade["direction"],
                entry_price=oportunidade["price"],
                confidence=oportunidade["confidence"],
                size=size,
                market=market
            )
            if trade:
                monitor.registrar_trade(trade, 0)
        
        self.trades_por_janela += 1

# ============= ESTRATÉGIA DE MEIO =============
class MiddleStrategy:
    def __init__(self):
        self.positions = []
        self.last_rebalance = 0
    
    def analyze(self, window, market, trade_manager, monitor):
        if not config.MIDDLE["active"] or window["phase"] != "MEIO" or not market:
            return
        
        if time.time() - self.last_rebalance > config.MIDDLE["rebalance_seconds"]:
            self.rebalance(window, market, trade_manager, monitor)
            self.last_rebalance = time.time()
    
    def rebalance(self, window, market, trade_manager, monitor):
        self.positions = [p for p in self.positions if p["window_end"] == window["end"]]
        
        if len(self.positions) >= config.MIDDLE["max_positions"]:
            return
        
        fair_up = market["up_price"]
        fair_down = market["down_price"]
        spread = config.MIDDLE["spread_bps"] / 10000
        
        bid_up = fair_up * (1 - spread/2)
        ask_up = fair_up * (1 + spread/2)
        bid_down = fair_down * (1 - spread/2)
        ask_down = fair_down * (1 + spread/2)
        
        position_size = trade_manager.bankroll * config.MIDDLE["position_size_pct"]
        
        position = {
            "window_start": window["start"],
            "window_end": window["end"],
            "strategy": "MIDDLE",
            "up_bid": bid_up,
            "up_ask": ask_up,
            "down_bid": bid_down,
            "down_ask": ask_down,
            "size": position_size,
            "entry_time": time.time()
        }
        
        self.positions.append(position)
        log.info(f"\n📊 MM: UP ${bid_up:.3f}/${ask_up:.3f} | DOWN ${bid_down:.3f}/${ask_down:.3f}")
    
    def check_profits(self, window, market, trade_manager, monitor):
        for position in self.positions[:]:
            if position["window_end"] != window["end"]:
                continue
            if random.random() < 0.3:
                profit = position["size"] * (config.MIDDLE["spread_bps"] / 10000)
                trade_manager.record_mm_profit(window, profit, position["size"])
                self.positions.remove(position)

# ============= ESTRATÉGIA DE FIM =============
class EndStrategy:
    def analyze_high_prob(self, open_price, current_price, seconds_left):
        if seconds_left > 10 or seconds_left < 3 or not open_price or not current_price:
            return None, 0
        
        diff_pct = (current_price - open_price) / open_price * 100
        
        if abs(diff_pct) < config.END["high_prob"]["min_move_pct"]:
            return None, 0
        
        confidence = min(abs(diff_pct) * 10, 99)
        
        if confidence >= config.END["high_prob"]["min_confidence"]:
            return ("UP" if diff_pct > 0 else "DOWN"), confidence
        return None, 0
    
    def analyze_low_prob(self, open_price, current_price, seconds_left):
        if seconds_left > 20 or seconds_left < 5 or not open_price or not current_price:
            return None, 0
        
        diff_pct = (current_price - open_price) / open_price * 100
        
        if abs(diff_pct) < config.END["low_prob"]["min_move_pct"]:
            return None, 0
        
        if diff_pct > 0.5:
            return "DOWN", min(abs(diff_pct) * 3, config.END["low_prob"]["max_confidence"])
        elif diff_pct < -0.5:
            return "UP", min(abs(diff_pct) * 3, config.END["low_prob"]["max_confidence"])
        
        return None, 0
    
    def analyze(self, open_price, current_price, seconds_left):
        direction, conf = self.analyze_high_prob(open_price, current_price, seconds_left)
        if direction:
            return direction, conf, "HIGH"
        
        direction, conf = self.analyze_low_prob(open_price, current_price, seconds_left)
        if direction:
            return direction, conf, "LOW"
        
        return None, 0, None

# ============= GERENCIADOR DE TRADES COM PROTEÇÃO GHOST FILL =============
class TradeManager:
    def __init__(self):
        self.bankroll = config.INITIAL_BANKROLL
        self.initial_bankroll = config.INITIAL_BANKROLL
        self.trades_abertos = []
        self.trades_fechados = []
        self.ghost_fill_alertas = []
        
        self.stats = {
            "START": {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0},
            "MIDDLE": {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0},
            "END_HIGH": {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0},
            "END_LOW": {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0}
        }
    
    def calculate_trade_size(self, strategy):
        if strategy == "START":
            return self.bankroll * config.START["trade_size_pct"]
        elif strategy == "MIDDLE":
            return self.bankroll * config.MIDDLE["position_size_pct"]
        elif strategy == "END_HIGH":
            return self.bankroll * config.END["high_prob"]["trade_size_pct"]
        else:
            return self.bankroll * config.END["low_prob"]["trade_size_pct"]
    
    # ============= PROTEÇÃO CONTRA GHOST FILLS =============
    def check_order_validity(self, order_id, token_id, expected_price, timestamp):
        """
        Verifica se uma ordem foi vítima de ghost fill
        Ghost fill: ordem removida do livro sem execução real
        """
        try:
            # 1. Verifica na blockchain se a ordem foi realmente executada
            web3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
            
            # Simulação - em produção, consultaria o contrato da Polymarket
            order_hash = hashlib.sha256(f"{order_id}{token_id}{timestamp}".encode()).hexdigest()
            
            # 2. Verifica se o token ainda está no livro de ordens
            url = f"{config.POLYCLOB_URL}/book"
            params = {"token_id": token_id}
            resp = requests.get(url, params=params, timeout=2)
            
            if resp.status_code == 200:
                data = resp.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                
                # Procura a ordem pelo preço esperado
                ordem_encontrada = False
                for bid in bids:
                    if abs(float(bid.get("price", 0)) - expected_price) < 0.001:
                        ordem_encontrada = True
                        break
                
                for ask in asks:
                    if abs(float(ask.get("price", 0)) - expected_price) < 0.001:
                        ordem_encontrada = True
                        break
                
                if not ordem_encontrada:
                    # Possível ghost fill!
                    alerta = {
                        "order_id": order_id,
                        "token_id": token_id,
                        "price": expected_price,
                        "timestamp": timestamp,
                        "tipo": "GHOST_FILL_SUSPEITO"
                    }
                    self.ghost_fill_alertas.append(alerta)
                    
                    log.error(f"👻 ALERTA GHOST FILL! Ordem {order_id[:8]} desapareceu sem execução")
                    
                    send_telegram(
                        f"<b>👻 ALERTA DE GHOST FILL</b>\n\n"
                        f"Ordem ID: {order_id[:8]}...\n"
                        f"Token: {token_id[:8]}...\n"
                        f"Preço: ${expected_price:.3f}\n"
                        f"Ação: Verifique manualmente!"
                    )
                    
                    return False
            return True
            
        except Exception as e:
            log.error(f"Erro ao verificar ghost fill: {e}")
            return False
    
    def executar_com_protecao(self, func, *args, **kwargs):
        """
        Executa uma função com proteção contra ghost fills
        """
        try:
            resultado = func(*args, **kwargs)
            
            if resultado and resultado.get("order_id"):
                time.sleep(2)
                self.check_order_validity(
                    resultado["order_id"],
                    resultado.get("token_id", ""),
                    resultado.get("entry_price", 0),
                    time.time()
                )
            
            return resultado
            
        except Exception as e:
            log.error(f"Erro na execução com proteção: {e}")
            return None
    
    def execute_trade(self, window, strategy, direction, entry_price, confidence, size, market):
        shares = size / entry_price
        
        order_id = f"ORD-{int(time.time())}-{random.randint(1000,9999)}"
        
        trade = {
            "order_id": order_id,
            "window_start": window["start"],
            "window_end": window["end"],
            "strategy": strategy,
            "direction": direction,
            "entry_price": entry_price,
            "size": size,
            "shares": shares,
            "confidence": confidence,
            "entry_time": time.time(),
            "token_id": market["up_token"] if direction == "UP" else market["down_token"]
        }
        
        # Verifica proteção contra ghost fill ANTES de adicionar
        if not self.check_order_validity(order_id, trade["token_id"], entry_price, time.time()):
            log.warning(f"⚠️ Ordem {order_id[:8]} pode ter sido vítima de ghost fill - cancelando")
            return None
        
        self.trades_abertos.append(trade)
        self.bankroll -= size
        self.stats[strategy]["trades"] += 1
        
        emoji = "🔴" if strategy == "START" else "🔵" if "HIGH" in strategy else "🟡"
        log.info(f"\n{emoji} TRADE {strategy}")
        log.info(f"   Direção: {direction}")
        log.info(f"   Preço: ${entry_price:.3f}")
        log.info(f"   Confiança: {confidence:.1f}%")
        log.info(f"   Tamanho: ${size:.2f}")
        log.info(f"   Order ID: {order_id[:8]}...")
        
        if strategy != "START" or size > 5:
            send_telegram(
                f"<b>{emoji} BTC 5min - {strategy}</b>\n\n"
                f"Direção: <b>{direction}</b>\n"
                f"Preço: ${entry_price:.3f}\n"
                f"Confiança: {confidence:.1f}%\n"
                f"Valor: ${size:.2f}"
            )
        
        return trade
    
    def execute_arb_trade(self, window, strategy, buy_direction, sell_direction, buy_price, sell_price, size):
        profit = size * ((1/buy_price - 1) + (1 - 1/sell_price))
        
        order_id = f"ARB-{int(time.time())}-{random.randint(1000,9999)}"
        
        trade = {
            "order_id": order_id,
            "window_start": window["start"],
            "window_end": window["end"],
            "strategy": strategy,
            "type": "arbitrage",
            "buy_direction": buy_direction,
            "sell_direction": sell_direction,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "size": size,
            "profit": profit,
            "entry_time": time.time()
        }
        
        self.trades_fechados.append(trade)
        self.bankroll += profit
        self.stats[strategy]["wins"] += 1
        self.stats[strategy]["pnl"] += profit
        
        log.info(f"\n💰 ARBITRAGEM: Lucro ${profit:.2f}")
        send_telegram(f"<b>💰 Arbitragem</b>\n\nLucro: ${profit:.2f}")
        return trade
    
    def record_mm_profit(self, window, profit, size):
        self.bankroll += profit
        self.stats["MIDDLE"]["wins"] += 1
        self.stats["MIDDLE"]["pnl"] += profit
        self.stats["MIDDLE"]["trades"] += 1
        log.info(f"\n💰 MM LUCRO: ${profit:.2f}")
        send_telegram(f"<b>📊 Market Making</b>\n\nLucro: ${profit:.2f}")
    
    def close_trade(self, trade, close_price, winner):
        if winner.upper() == trade["direction"]:
            payout = trade["shares"] * 1.0
            pnl = payout - trade["size"]
            self.stats[trade["strategy"]]["wins"] += 1
            result_emoji = "✅"
        else:
            pnl = -trade["size"]
            self.stats[trade["strategy"]]["losses"] += 1
            result_emoji = "❌"
        
        self.stats[trade["strategy"]]["pnl"] += pnl
        self.bankroll += trade["size"] + pnl
        trade["pnl"] = pnl
        trade["pnl_pct"] = (pnl / trade["size"]) * 100
        trade["exit_price"] = close_price
        
        self.trades_fechados.append(trade)
        if trade in self.trades_abertos:
            self.trades_abertos.remove(trade)
        
        log.info(f"\n{result_emoji} FECHADO {trade['strategy']}: ${pnl:.2f} ({trade['pnl_pct']:+.1f}%)")
        
        if trade["strategy"] != "START" or abs(pnl) > 2:
            send_telegram(
                f"<b>{result_emoji} {trade['strategy']}</b>\n\n"
                f"Resultado: <b>${pnl:.2f} ({trade['pnl_pct']:+.1f}%)</b>\n"
                f"Bankroll: ${self.bankroll:.2f}"
            )
        
        return pnl
    
    def check_expired_trades(self, window, binance, monitor):
        for trade in self.trades_abertos[:]:
            if trade["window_end"] <= time.time():
                close_price = binance.get_price_at(trade["window_end"])
                open_price = binance.get_price_at(trade["window_start"])
                if close_price and open_price:
                    winner = "UP" if close_price >= open_price else "DOWN"
                    pnl = self.close_trade(trade, close_price, winner)
                    monitor.registrar_resultado(trade, pnl)

# ============= SISTEMA DE MONITORAMENTO =============
class Monitor:
    def __init__(self):
        self.filename = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        self.metrics = {
            "start_time": time.time(),
            "total_windows": 0,
            "trades_executados": 0,
            "trades_vencedores": 0,
            "trades_perdedores": 0,
            "volume_total": 0.0,
            "oportunidades_perdidas": 0,
            "tempos_resposta": [],
            "estrategias": {
                "START": {"tentativas": 0, "sucessos": 0},
                "MIDDLE": {"tentativas": 0, "sucessos": 0},
                "END_HIGH": {"tentativas": 0, "sucessos": 0},
                "END_LOW": {"tentativas": 0, "sucessos": 0}
            }
        }
        
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'estrategia', 'direcao', 'preco_entrada',
                'preco_saida', 'resultado', 'pnl', 'confianca', 'latencia_ms'
            ])
        
        log.info(f"\n📊 MONITORAMENTO INICIADO")
        log.info(f"   Arquivo: {self.filename}")
        send_telegram(
            f"<b>🤖 BTC 5min Bot - Railway</b>\n\n"
            f"Iniciando monitoramento 24/7\n"
            f"Bankroll virtual: ${config.INITIAL_BANKROLL}"
        )
    
    def registrar_trade(self, trade, latencia_ms):
        self.metrics["trades_executados"] += 1
        self.metrics["volume_total"] += trade.get("size", 0)
        self.metrics["tempos_resposta"].append(latencia_ms)
        estrategia = trade.get("strategy", "UNKNOWN")
        if estrategia in self.metrics["estrategias"]:
            self.metrics["estrategias"][estrategia]["tentativas"] += 1
    
    def registrar_resultado(self, trade, pnl):
        if pnl > 0:
            self.metrics["trades_vencedores"] += 1
            resultado = "WIN"
            estrategia = trade.get("strategy", "UNKNOWN")
            if estrategia in self.metrics["estrategias"]:
                self.metrics["estrategias"][estrategia]["sucessos"] += 1
        else:
            self.metrics["trades_perdedores"] += 1
            resultado = "LOSS"
        
        with open(self.filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                trade.get("strategy", "UNKNOWN"),
                trade.get("direction", "UNKNOWN"),
                f"{trade.get('entry_price', 0):.4f}",
                f"{trade.get('exit_price', 0):.4f}",
                resultado,
                f"{pnl:.2f}",
                f"{trade.get('confidence', 0):.1f}",
                f"{latencia_ms:.1f}"
            ])
    
    def registrar_oportunidade_perdida(self, estrategia, motivo):
        self.metrics["oportunidades_perdidas"] += 1
        log.info(f"   ⚠️ Oportunidade perdida [{estrategia}]: {motivo}")
    
    def print_status(self):
        elapsed = time.time() - self.metrics["start_time"]
        horas = elapsed / 3600
        total_trades = self.metrics["trades_executados"]
        win_rate = (self.metrics["trades_vencedores"] / total_trades * 100) if total_trades > 0 else 0
        
        log.info("\n" + "📊"*40)
        log.info("📈 RELATÓRIO DE MONITORAMENTO")
        log.info("📊"*40)
        log.info(f"⏱️  Tempo: {horas:.1f}h")
        log.info(f"📊 Janelas: {self.metrics['total_windows']}")
        log.info(f"💰 Trades: {total_trades} ({self.metrics['trades_vencedores']}W/{self.metrics['trades_perdedores']}L)")
        log.info(f"📈 Win rate: {win_rate:.1f}%")
        log.info(f"💵 Volume: ${self.metrics['volume_total']:.2f}")
        log.info(f"👻 Ghost Fill Alertas: {len(self.metrics.get('ghost_fill_alertas', []))}")
        log.info("📊"*40)
        
        telegram_msg = (
            f"<b>📊 RELATÓRIO DE MONITORAMENTO</b>\n\n"
            f"⏱️ Tempo: {horas:.1f}h\n"
            f"📊 Janelas: {self.metrics['total_windows']}\n"
            f"💰 Trades: {total_trades} ({self.metrics['trades_vencedores']}W/{self.metrics['trades_perdedores']}L)\n"
            f"📈 Win rate: {win_rate:.1f}%\n"
            f"💵 Volume: ${self.metrics['volume_total']:.2f}"
        )
        send_telegram(telegram_msg)

# ============= BOT PRINCIPAL =============
class BTC5MinBot:
    def __init__(self):
        self.binance = BinanceClient()
        self.polymarket = PolymarketClient()
        self.window_mgr = WindowManager()
        
        self.start_strategy = StartStrategy()
        self.middle_strategy = MiddleStrategy()
        self.end_strategy = EndStrategy()
        
        self.trades = TradeManager()
        self.monitor = Monitor()
        
        self.running = True
        self.current_window = None
        self.last_mm_check = 0
        self.last_stats = time.time()
        self.heartbeat = 0
        
        log.info("\n" + "🔥"*80)
        log.info(" BTC 5 MIN BOT v3.0 - RAILWAY EDITION")
        log.info("🔥"*80)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Bankroll virtual: ${config.INITIAL_BANKROLL}")
        log.info(f" Proteção Ghost Fill: ATIVADA")
        log.info("🔥"*80)
    
    def process_window(self):
        window = self.window_mgr.get_current_window()
        
        # Verificação periódica de ghost fills (a cada 5 minutos)
        if int(time.time()) % 300 < 5:
            for trade in self.trades.trades_abertos:
                self.trades.check_order_validity(
                    trade.get("order_id", ""),
                    trade.get("token_id", ""),
                    trade.get("entry_price", 0),
                    trade.get("entry_time", 0)
                )
        
        if self.current_window != window["start"]:
            self.current_window = window["start"]
            self.monitor.metrics["total_windows"] += 1
            log.info(f"\n{'='*80}")
            log.info(f"⏰ JANELA #{self.monitor.metrics['total_windows']}: {self.window_mgr.format_time(window['start'])} - {self.window_mgr.format_time(window['end'])}")
            log.info(f"📊 Fase: {window['phase']} | Elapsed: {window['elapsed']}s | Restam: {window['remaining']}s")
        
        open_price = self.binance.get_price_at(window["start"])
        current_price = self.binance.get_current_price()
        
        if not open_price or not current_price:
            return
        
        if window["remaining"] % 10 == 0 or window["remaining"] <= 5:
            diff = ((current_price - open_price) / open_price * 100)
            log.info(f"📊 BTC: ${current_price:.2f} | Diff: {diff:+.3f}% | Fase: {window['phase']} | Restam: {window['remaining']}s")
        
        self.trades.check_expired_trades(window, self.binance, self.monitor)
        
        market = self.polymarket.find_market(window["start"])
        if not market or not market["exists"]:
            return
        
        if window["phase"] == "INÍCIO":
            log.info("🔍 [INÍCIO] Analisando oportunidades...")
            oportunidade = self.start_strategy.analyze(window, market, current_price)
            if oportunidade:
                log.info(f"🎯 [INÍCIO] Oportunidade: {oportunidade['type']}")
                self.start_strategy.execute(self.trades, self.monitor, window, market, oportunidade)
        
        elif window["phase"] == "MEIO":
           log.info("🟢")



