#!/usr/bin/env python3
"""
=================================================================
    BTC 5 MIN BOT v3.0 - MODO MONITORAMENTO
    FASE 1: 24-48 horas de coleta de dados
    Sem dinheiro real - apenas simulação e análise
    Versão FINAL com Telegram e Web Server para Render
=================================================================
"""

import os
import time
import json
import logging
import requests
import random
import csv
from datetime import datetime, timedelta
from collections import deque
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    # Modo de operação - SEMPRE SIMULAÇÃO no monitoramento
    SIMULATION_MODE = True
    
    # Banca virtual para teste
    INITIAL_BANKROLL = 100.0
    
    # ===== ESTRATÉGIA DE INÍCIO (0-60s) =====
    START = {
        "active": True,
        "window": [0, 60],
        "trade_size_pct": 0.005,  # 0.5% da banca
        "min_spread": 0.02,        # 2% spread mínimo
        "max_trades_per_window": 3,
        "profit_target": 0.02,
        "stop_loss": 0.01
    }
    
    # ===== ESTRATÉGIA DE MEIO (60-240s) =====
    MIDDLE = {
        "active": True,
        "window": [60, 240],
        "position_size_pct": 0.02,  # 2% da banca por lado
        "spread_bps": 20,            # 0.2% de spread
        "rebalance_seconds": 30,
        "max_positions": 3
    }
    
    # ===== ESTRATÉGIA DE FIM (240-300s) =====
    END = {
        "active": True,
        "window": [240, 300],
        "high_prob": {
            "min_confidence": 85,        # 85%+ certeza
            "max_entry_price": 0.95,      # Máx $0.95
            "trade_size_pct": 0.02,       # 2% da banca
            "min_move_pct": 0.08          # 0.08% mínimo
        },
        "low_prob": {
            "max_confidence": 20,         # Máx 20% certeza
            "min_entry_price": 0.01,       # Mín $0.01
            "max_entry_price": 0.08,       # Máx $0.08
            "trade_size_pct": 0.005,       # 0.5% da banca
            "min_move_pct": 0.5            # 0.5% mínimo
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
        log.warning("⚠️ Telegram não configurado. Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID")
        return
    
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            log.info("📤 Mensagem Telegram enviada")
        else:
            log.error(f"❌ Erro Telegram: {response.text}")
    except Exception as e:
        log.error(f"❌ Erro ao enviar Telegram: {e}")

# ============= CLIENTES API =============
class BinanceClient:
    @staticmethod
    def get_current_price():
        try:
            url = f"{config.BINANCE_URL}?symbol=BTCUSDT&interval=1m&limit=1"
            resp = requests.get(url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][4])  # Preço de fechamento
        except Exception as e:
            log.debug(f"Erro Binance: {e}")
        return None
    
    @staticmethod
    def get_price_at(timestamp):
        try:
            url = f"{config.BINANCE_URL}?symbol=BTCUSDT&interval=1m&startTime={timestamp*1000}&limit=1"
            resp = requests.get(url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][4])
        except Exception as e:
            log.debug(f"Erro Binance: {e}")
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
        except Exception as e:
            log.debug(f"Erro OrderBook: {e}")
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
        except Exception as e:
            log.debug(f"Erro find_market: {e}")
            return None

# ============= GERENCIADOR DE JANELAS =============
class WindowManager:
    @staticmethod
    def get_current_window():
        now = int(time.time())
        window_start = now - (now % 300)
        window_end = window_start + 300
        elapsed = now - window_start
        
        return {
            "start": window_start,
            "end": window_end,
            "remaining": window_end - now,
            "elapsed": elapsed,
            "phase": WindowManager.get_phase(elapsed),
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
        
        # Arbitragem UP/DOWN
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
        
        # Scalping direcional
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
            
            if random.random() < 0.3:  # 30% chance de execução
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
        # Tenta HIGH primeiro
        direction, conf = self.analyze_high_prob(open_price, current_price, seconds_left)
        if direction:
            return direction, conf, "HIGH"
        
        # Depois LOW
        direction, conf = self.analyze_low_prob(open_price, current_price, seconds_left)
        if direction:
            return direction, conf, "LOW"
        
        return None, 0, None

# ============= GERENCIADOR DE TRADES =============
class TradeManager:
    def __init__(self):
        self.bankroll = config.INITIAL_BANKROLL
        self.initial_bankroll = config.INITIAL_BANKROLL
        self.trades_abertos = []
        self.trades_fechados = []
        
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
    
    def execute_trade(self, window, strategy, direction, entry_price, confidence, size, market):
        shares = size / entry_price
        
        trade = {
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
        
        self.trades_abertos.append(trade)
        self.bankroll -= size
        self.stats[strategy]["trades"] += 1
        
        emoji = "🔴" if strategy == "START" else "🔵" if "HIGH" in strategy else "🟡"
        log.info(f"\n{emoji} TRADE {strategy}")
        log.info(f"   Direção: {direction}")
        log.info(f"   Preço: ${entry_price:.3f}")
        log.info(f"   Confiança: {confidence:.1f}%")
        log.info(f"   Tamanho: ${size:.2f}")
        
        # Telegram para trades importantes
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
        
        trade = {
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
        
        send_telegram(
            f"<b>💰 Arbitragem</b>\n\n"
            f"Compra: {buy_direction} @ ${buy_price:.3f}\n"
            f"Venda: {sell_direction} @ ${sell_price:.3f}\n"
            f"Lucro: ${profit:.2f}"
        )
        
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
            resultado = "LUCRO"
        else:
            pnl = -trade["size"]
            self.stats[trade["strategy"]]["losses"] += 1
            result_emoji = "❌"
            resultado = "PREJUÍZO"
        
        self.stats[trade["strategy"]]["pnl"] += pnl
        self.bankroll += trade["size"] + pnl
        trade["pnl"] = pnl
        trade["pnl_pct"] = (pnl / trade["size"]) * 100
        trade["exit_price"] = close_price
        
        self.trades_fechados.append(trade)
        if trade in self.trades_abertos:
            self.trades_abertos.remove(trade)
        
        log.info(f"\n{result_emoji} FECHADO {trade['strategy']}: ${pnl:.2f} ({trade['pnl_pct']:+.1f}%)")
        
        # Telegram para resultados importantes
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
        # Cria arquivo CSV com timestamp
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
        
        # Cabeçalho do CSV
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'estrategia', 'direcao', 'preco_entrada',
                'preco_saida', 'resultado', 'pnl', 'confianca', 'latencia_ms'
            ])
        
        log.info(f"\n📊 MONITORAMENTO INICIADO")
        log.info(f"   Arquivo: {self.filename}")
        log.info(f"   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Notifica início via Telegram
        send_telegram(
            f"<b>🤖 BTC 5min Bot - Monitoramento</b>\n\n"
            f"Iniciando coleta de 24-48h\n"
            f"Bankroll virtual: ${config.INITIAL_BANKROLL}\n"
            f"Arquivo: {self.filename}"
        )
    
    def registrar_trade(self, trade, latencia_ms):
        """Registra trade executado"""
        self.metrics["trades_executados"] += 1
        self.metrics["volume_total"] += trade.get("size", 0)
        self.metrics["tempos_resposta"].append(latencia_ms)
        
        estrategia = trade.get("strategy", "UNKNOWN")
        if estrategia in self.metrics["estrategias"]:
            self.metrics["estrategias"][estrategia]["tentativas"] += 1
    
    def registrar_resultado(self, trade, pnl):
        """Registra resultado do trade"""
        if pnl > 0:
            self.metrics["trades_vencedores"] += 1
            resultado = "WIN"
            estrategia = trade.get("strategy", "UNKNOWN")
            if estrategia in self.metrics["estrategias"]:
                self.metrics["estrategias"][estrategia]["sucessos"] += 1
        else:
            self.metrics["trades_perdedores"] += 1
            resultado = "LOSS"
        
        # Salva no CSV
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
        """Registra oportunidade que não foi executada"""
        self.metrics["oportunidades_perdidas"] += 1
        log.info(f"   ⚠️ Oportunidade perdida [{estrategia}]: {motivo}")
    
    def get_relatorio(self):
        """Gera relatório completo"""
        elapsed = time.time() - self.metrics["start_time"]
        horas = elapsed / 3600
        
        total_trades = self.metrics["trades_executados"]
        win_rate = (self.metrics["trades_vencedores"] / total_trades * 100) if total_trades > 0 else 0
        
        tempo_medio = sum(self.metrics["tempos_resposta"]) / len(self.metrics["tempos_resposta"]) if self.metrics["tempos_resposta"] else 0
        
        return {
            "tempo_rodando": f"{horas:.1f}h",
            "janelas": self.metrics["total_windows"],
            "trades_total": total_trades,
            "wins": self.metrics["trades_vencedores"],
            "losses": self.metrics["trades_perdedores"],
            "win_rate": f"{win_rate:.1f}%",
            "volume": f"${self.metrics['volume_total']:.2f}",
            "tempo_medio_resposta": f"{tempo_medio:.1f}ms",
            "oportunidades_perdidas": self.metrics["oportunidades_perdidas"],
            "estrategias": self.metrics["estrategias"]
        }
    
    def print_status(self):
        """Mostra status atual"""
        rel = self.get_relatorio()
        
        log.info("\n" + "📊"*40)
        log.info("📈 RELATÓRIO DE MONITORAMENTO")
        log.info("📊"*40)
        log.info(f"⏱️  Tempo: {rel['tempo_rodando']}")
        log.info(f"📊 Janelas: {rel['janelas']}")
        log.info(f"💰 Trades: {rel['trades_total']} ({rel['wins']}W/{rel['losses']}L)")
        log.info(f"📈 Win rate: {rel['win_rate']}")
        log.info(f"💵 Volume: {rel['volume']}")
        log.info(f"⚡ Latência: {rel['tempo_medio_resposta']}")
        log.info(f"🎯 Oportunidades perdidas: {rel['oportunidades_perdidas']}")
        log.info("-"*40)
        log.info("📊 Detalhamento por estratégia:")
        for est, dados in rel['estrategias'].items():
            if dados['tentativas'] > 0:
                taxa = (dados['sucessos'] / dados['tentativas'] * 100) if dados['tentativas'] > 0 else 0
                log.info(f"   {est}: {dados['tentativas']} tentativas | {taxa:.1f}% sucesso")
        log.info("📊"*40)

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
        
        log.info("\n" + "🔥"*80)
        log.info(" BTC 5 MIN BOT v3.0 - MODO MONITORAMENTO")
        log.info("🔥"*80)
        log.info(f" Modo: SIMULAÇÃO (sem dinheiro real)")
        log.info(f" Bankroll virtual: ${config.INITIAL_BANKROLL}")
        log.info(f" Monitorando: {self.monitor.filename}")
        log.info("🔥"*80)
    
    def process_window(self):
        window = self.window_mgr.get_current_window()
        
        # Nova janela
        if self.current_window != window["start"]:
            self.current_window = window["start"]
            self.monitor.metrics["total_windows"] += 1
            
            log.info(f"\n{'='*80}")
            log.info(f"⏰ JANELA #{self.monitor.metrics['total_windows']}: "
                    f"{self.window_mgr.format_time(window['start'])} - "
                    f"{self.window_mgr.format_time(window['end'])}")
            log.info(f"📊 Fase: {window['phase']} ({window['elapsed']}s) | "
                    f"Restam: {window['remaining']}s")
        
        # Preços
        open_price = self.binance.get_price_at(window["start"])
        current_price = self.binance.get_current_price()
        
        if not open_price or not current_price:
            return
        
        # Log periódico
        if window["remaining"] % 10 == 0 or window["remaining"] <= 5:
            diff = ((current_price - open_price) / open_price * 100)
            log.info(f"📊 BTC: ${current_price:.2f} | Diff: {diff:+.3f}% | "
                    f"Fase: {window['phase']} | Restam: {window['remaining']}s")
        
        # Fecha trades expirados
        self.trades.check_expired_trades(window, self.binance, self.monitor)
        
        # Busca mercado
        market = self.polymarket.find_market(window["start"])
        if not market or not market["exists"]:
            return
        
        # ===== INÍCIO =====
        if window["phase"] == "INÍCIO":
            oportunidade = self.start_strategy.analyze(window, market, current_price)
            if oportunidade:
                self.start_strategy.execute(self.trades, self.monitor, window, market, oportunidade)
            else:
                self.monitor.registrar_oportunidade_perdida("START", "Nenhuma oportunidade")
        
        # ===== MEIO =====
        elif window["phase"] == "MEIO":
            self.middle_strategy.analyze(window, market, self.trades, self.monitor)
            
            if time.time() - self.last_mm_check > 10:
                self.middle_strategy.check_profits(window, market, self.trades, self.monitor)
                self.last_mm_check = time.time()
        
        # ===== FIM =====
        elif window["phase"] == "FIM":
            if len([t for t in self.trades.trades_abertos if t["strategy"] == "MIDDLE"]) == 0:
                direction, confidence, sub = self.end_strategy.analyze(
                    open_price, current_price, window["remaining"]
                )
                
                if direction and sub:
                    strategy = f"END_{sub}"
                    price = market["up_price"] if direction == "UP" else market["down_price"]
                    
                    # Validação
                    if sub == "HIGH":
                        if price > config.END["high_prob"]["max_entry_price"]:
                            self.monitor.registrar_oportunidade_perdida(strategy, f"Preço alto {price:.3f}")
                            return
                        size = self.trades.calculate_trade_size("END_HIGH")
                    else:
                        if price < config.END["low_prob"]["min_entry_price"] or price > config.END["low_prob"]["max_entry_price"]:
                            self.monitor.registrar_oportunidade_perdida(strategy, f"Preço fora range {price:.3f}")
                            return
                        size = self