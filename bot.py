import os
import time
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
import requests
import pandas as pd
import numpy as np

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lightweight HTTP Health Check Server for Render Cloud Web Service compatibility
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"PURE PYTHON ALGORITHMIC BOT ENGINE ONLINE - 24/7 ACTIVE")

    def log_message(self, format, *args):
        return  # Suppress default HTTP logs

def start_health_server():
    port = int(os.environ.get('PORT', 10000))
    logging.info(f"Starting Cloud Health Check HTTP Server on port {port}...")
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        logging.error(f"Health server error: {e}")

class PurePythonTradingBot:
    def __init__(self):
        self.symbol = 'BTCUSDT'
        self.interval = '1m'
        self.trade_usd_size = float(os.environ.get('TRADE_USD_SIZE', 10.0))
        self.status = 'ACTIVE'
        self.trading_mode = os.environ.get('TRADING_MODE', 'TESTNET')
        
        # Strategy Parameters
        self.rsi_period = 14
        self.rsi_buy_threshold = 30.0
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.volume_ma_period = 20
        self.volume_spike_multiplier = 1.5
        self.adx_period = 14
        self.adx_buy_threshold = 25.0

        # Account & Position State
        self.balance = 1000.0
        self.position_open = False
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0

        logging.info("Pure Python Algorithmic Bot initialized with Cloud 24/7 Engine.")

    def fetch_binance_klines(self, symbol, interval, limit=100):
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        try:
            res = requests.get(url, timeout=5)
            data = res.json()
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)
            return df
        except Exception as e:
            logging.error(f"Error fetching Binance klines: {e}")
            return None

    def calc_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calc_macd(self, series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line

    def run_strategy_step(self):
        df_1m = self.fetch_binance_klines(self.symbol, '1m', 100)
        if df_1m is None or len(df_1m) < 30:
            return

        current_price = df_1m['close'].iloc[-1]
        
        # Calculate Indicators
        df_1m['rsi'] = self.calc_rsi(df_1m['close'], self.rsi_period)
        macd_line, signal_line = self.calc_macd(df_1m['close'], self.macd_fast, self.macd_slow, self.macd_signal)
        
        current_rsi = df_1m['rsi'].iloc[-1]
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]

        vol_ma = df_1m['volume'].rolling(self.volume_ma_period).mean().iloc[-1]
        current_vol = df_1m['volume'].iloc[-1]
        is_vol_spike = current_vol > (vol_ma * self.volume_spike_multiplier)

        # Condition Evaluation
        cond_rsi = current_rsi < self.rsi_buy_threshold
        cond_macd = current_macd > current_signal
        cond_vol = is_vol_spike

        matched_count = sum([cond_rsi, cond_macd, cond_vol])
        logging.info(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] BTC: ${current_price:.2f} | RSI: {current_rsi:.1f} | Signals: {matched_count}/3 Matched")

    def run(self):
        logging.info("Bot execution loop started at sub-second speed.")
        while True:
            try:
                self.run_strategy_step()
            except Exception as e:
                logging.error(f"Error in main bot loop: {e}")
            time.sleep(1)

if __name__ == '__main__':
    # Start Cloud Health Server in background daemon thread
    threading.Thread(target=start_health_server, daemon=True).start()

    # Start Main Algorithmic Trading Bot
    bot = PurePythonTradingBot()
    bot.run()
