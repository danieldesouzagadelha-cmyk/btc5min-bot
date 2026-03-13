#!/usr/bin/env python3
"""
=================================================================
    BOT BTC 5MIN - ESTRATÉGIA DOS 10 SEGUNDOS
    Baseado em traders que lucram consistentemente
=================================================================
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============= CONFIGURAÇÕES =============
class Config:
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    CAPITAL = float(os.getenv("CAPITAL", "50.0"))
    
    # Estratégia dos 10 segundos
    TRADE_SIZE = 10.0              # $10 por trade
    MIN_MOVE_PCT = 0.08             # 0.08% mínimo
    ENTRY_PRICE_MAX = 0.95           # Máximo $0.95 (lucro 5%+)
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

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

# ============= CLIENTE BINANCE =============
class BinanceClient:
    @staticmethod
    def get_current_price():
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = requests.get(url, timeout=2)
            return float(resp.json()["price"])
        except:
            return None
    
    @staticmethod
    def get_price_at(timestamp):
        try:
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": "BTCUSDT",
                "interval": "1m",
                "startTime": timestamp * 1000,
                "limit": 1
            }
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][4])  # Preço de fechamento
        except:
            pass
        return None

# ============= GERENCIADOR DE JANELAS =============
class WindowManager:
    @staticmethod
    def get_current_window():
        now = int(time.time())
        window_start = now - (now % 300)
        window_end = window_start + 300
        
        return {
            "start": window_start,
            "end": window_end,
            "remaining": window_end - now,
            "elapsed": now - window_start,
            "start_str": datetime.fromtimestamp(window_start).strftime("%H:%M:%S"),
            "end_str": datetime.fromtimestamp(window_end).strftime("%H:%M:%S")
        }

# ============= ESTRATÉGIA DOS 10 SEGUNDOS =============
class TenSecondStrategy:
    def __init__(self):
        self.bankroll = config.CAPITAL
        self.initial = config.CAPITAL
        self.trade_open = False
        self.current_trade = None
        self.wins = 0
        self.losses = 0
        self.pnl = 0.0
        self.last_window = 0
    
    def analyze(self, window, open_price, current_price):
        """Analisa oportunidade nos últimos 10 segundos"""
        
        # Só nos últimos 10 segundos
        if window["remaining"] > 10 or window["remaining"] < 3:
            return None
        
        if not open_price or not current_price:
            return None
        
        # Calcula diferença percentual
        diff_pct = (current_price - open_price) / open_price * 100
        
        # Log da análise
        log.info(f"🔍 Últimos {window['remaining']}s - BTC: ${current_price:.2f} | Diff: {diff_pct:+.3f}%")
        
        # Verifica se movimento é significativo
        if abs(diff_pct) < config.MIN_MOVE_PCT:
            return None
        
        # Define direção e confiança
        if diff_pct > 0:
            direction = "UP"
            confidence = min(abs(diff_pct) * 10, 95)
            log.info(f"🎯 OPORTUNIDADE: UP com {confidence:.1f}% de confiança")
        else:
            direction = "DOWN"
            confidence = min(abs(diff_pct) * 10, 95)
            log.info(f"🎯 OPORTUNIDADE: DOWN com {confidence:.1f}% de confiança")
        
        return {
            "direction": direction,
            "confidence": confidence,
            "diff_pct": diff_pct,
            "entry_price": current_price
        }
    
    def execute_trade(self, window, opportunity):
        """Executa trade"""
        if self.trade_open:
            return
        
        # Define preço de entrada (maker)
        entry_price = config.ENTRY_PRICE_MAX
        size = config.TRADE_SIZE
        shares = size / entry_price
        
        trade = {
            "window_start": window["start"],
            "window_end": window["end"],
            "direction": opportunity["direction"],
            "entry_price": entry_price,
            "size": size,
            "shares": shares,
            "confidence": opportunity["confidence"],
            "entry_time": time.time()
        }
        
        self.trade_open = True
        self.current_trade = trade
        self.bankroll -= size
        
        log.info(f"\n💰 TRADE EXECUTADO!")
        log.info(f"   Direção: {trade['direction']}")
        log.info(f"   Preço: ${entry_price:.3f}")
        log.info(f"   Tamanho: ${size:.2f}")
        log.info(f"   Confiança: {trade['confidence']:.1f}%")
        
        send_telegram(
            f"<b>🟢 BTC 5min - COMPRA</b>\n\n"
            f"Direção: {trade['direction']}\n"
            f"Preço: ${entry_price:.3f}\n"
            f"Confiança: {trade['confidence']:.1f}%\n"
            f"Valor: ${size:.2f}"
        )
        
        return trade
    
    def check_result(self, window, close_price):
        """Verifica resultado do trade"""
        if not self.trade_open:
            return
        
        open_price = BinanceClient.get_price_at(self.current_trade["window_start"])
        if not open_price:
            return
        
        winner = "UP" if close_price >= open_price else "DOWN"
        
        if winner == self.current_trade["direction"]:
            payout = self.current_trade["shares"] * 1.0
            pnl = payout - self.current_trade["size"]
            self.wins += 1
            result_emoji = "✅"
            result_text = "LUCRO"
        else:
            pnl = -self.current_trade["size"]
            self.losses += 1
            result_emoji = "❌"
            result_text = "PREJUÍZO"
        
        self.pnl += pnl
        self.bankroll += self.current_trade["size"] + pnl
        
        log.info(f"\n{result_emoji} TRADE FECHADO")
        log.info(f"   Direção: {self.current_trade['direction']}")
        log.info(f"   Preço fim: ${close_price:.2f}")
        log.info(f"   Vencedor: {winner}")
        log.info(f"   PnL: ${pnl:.2f}")
        log.info(f"   Bankroll: ${self.bankroll:.2f}")
        
        send_telegram(
            f"<b>{result_emoji} BTC 5min - {result_text}</b>\n\n"
            f"Direção: {self.current_trade['direction']}\n"
            f"Entrada: ${self.current_trade['entry_price']:.3f}\n"
            f"Saída: ${close_price:.2f}\n"
            f"PnL: ${pnl:.2f}\n"
            f"Bankroll: ${self.bankroll:.2f}"
        )
        
        self.trade_open = False
        self.current_trade = None
    
    def get_stats(self):
        total = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0
        retorno = ((self.bankroll - self.initial) / self.initial) * 100
        
        return {
            "bankroll": self.bankroll,
            "retorno": retorno,
            "total": total,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": win_rate,
            "pnl": self.pnl
        }
    
    def print_stats(self):
        s = self.get_stats()
        
        log.info("\n" + "="*60)
        log.info("📊 ESTATÍSTICAS")
        log.info("="*60)
        log.info(f"💰 Bankroll: ${s['bankroll']:.2f} ({s['retorno']:+.1f}%)")
        log.info(f"📈 Trades: {s['total']} ({s['wins']}W/{s['losses']}L)")
        log.info(f"🎯 Win rate: {s['win_rate']:.1f}%")
        log.info(f"💵 PnL: ${s['pnl']:.2f}")
        log.info("="*60)

# ============= BOT PRINCIPAL =============
class BTC5MinBot:
    def __init__(self):
        self.window = WindowManager()
        self.strategy = TenSecondStrategy()
        self.running = True
        self.current_window = None
        self.heartbeat = 0
        
        log.info("\n" + "🚀"*60)
        log.info(" BTC 5 MIN BOT - ESTRATÉGIA DOS 10 SEGUNDOS")
        log.info("🚀"*60)
        log.info(f" Modo: {'SIMULAÇÃO' if config.SIMULATION_MODE else 'REAL'}")
        log.info(f" Bankroll: ${config.CAPITAL}")
        log.info(f" Trade size: ${config.TRADE_SIZE}")
        log.info(f" Movimento mínimo: {config.MIN_MOVE_PCT}%")
        log.info("🚀"*60)
        
        send_telegram(
            f"<b>🤖 BTC 5 MIN BOT INICIADO</b>\n\n"
            f"Bankroll: ${config.CAPITAL}\n"
            f"Trade size: ${config.TRADE_SIZE}\n"
            f"Estratégia: 10 segundos"
        )
    
    def run(self):
        log.info("\n🚀 BOT OPERANDO - Monitorando BTC...\n")
        
        try:
            while self.running:
                window = self.window.get_current_window()
                
                # Nova janela
                if self.current_window != window["start"]:
                    self.current_window = window["start"]
                    log.info(f"\n{'='*60}")
                    log.info(f"⏰ JANELA: {window['start_str']} - {window['end_str']}")
                    
                    # Reseta trade se necessário
                    if self.strategy.trade_open and time.time() > self.strategy.current_trade["window_end"]:
                        close_price = BinanceClient.get_price_at(window["start"]) or BinanceClient.get_current_price()
                        if close_price:
                            self.strategy.check_result(window, close_price)
                
                # Preços
                open_price = BinanceClient.get_price_at(window["start"])
                current_price = BinanceClient.get_current_price()
                
                if not open_price or not current_price:
                    time.sleep(1)
                    continue
                
                # Se não tem trade aberto, analisa oportunidade
                if not self.strategy.trade_open:
                    opportunity = self.strategy.analyze(window, open_price, current_price)
                    if opportunity:
                        self.strategy.execute_trade(window, opportunity)
                
                # Heartbeat
                self.heartbeat += 1
                if self.heartbeat % 60 == 0:
                    status = "ABERTA" if self.strategy.trade_open else "FECHADA"
                    log.info(f"💓 Heartbeat - Posição: {status}")
                
                # Estatísticas a cada 10 minutos
                if self.heartbeat % 600 == 0:
                    self.strategy.print_stats()
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        self.running = False
        log.info("\n🛑 Bot parado")
        self.strategy.print_stats()
        send_telegram(
            f"<b>🛑 BTC 5 MIN BOT PARADO</b>\n\n"
            f"PnL Final: ${self.strategy.pnl:.2f}\n"
            f"Bankroll: ${self.strategy.bankroll:.2f}"
        )

# ============= MAIN =============
if __name__ == "__main__":
    bot = BTC5MinBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
