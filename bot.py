import os
import sys
import time
import asyncio
import logging
import datetime
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from binance.client import Client
from binance.exceptions import BinanceAPIException

from config import (
    TRADING_MODE,
    SYMBOL,
    DATABASE_URL,
    TripleLockSafetyValidator,
    get_binance_client,
)
from telegram_bot import send_telegram_alert

logger = logging.getLogger("AlgorithmicTradingBot")

# Pure Pandas/Numpy Technical Indicator Helper Functions
def calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def calc_ema(series: pd.Series, length=200) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def calc_atr(df: pd.DataFrame, length=14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_cp = (df["high"] - df["close"].shift(1)).abs()
    low_cp = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def calc_adx(df: pd.DataFrame, length=14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    pos_dm = np.where((up > down) & (up > 0), up, 0.0)
    neg_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr = calc_atr(df, length)
    pos_di = 100 * (pd.Series(pos_dm).ewm(alpha=1/length, adjust=False).mean() / (atr + 1e-10))
    neg_di = 100 * (pd.Series(neg_dm).ewm(alpha=1/length, adjust=False).mean() / (atr + 1e-10))
    dx = 100 * ((pos_di - neg_di).abs() / (pos_di + neg_di + 1e-10))
    return dx.ewm(alpha=1/length, adjust=False).mean()

class AlgorithmicTradingBot:
    def __init__(self):
        self.symbol = SYMBOL
        self.client = get_binance_client()
        # Execute Triple-Lock Safety Validation
        TripleLockSafetyValidator.validate_environment(self.client)
        logger.info(f"Initialized Algorithmic Trading Bot on {SYMBOL} [{TRADING_MODE}]")

    def get_db_connection(self):
        """Creates a PostgreSQL/Supabase database connection."""
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def load_bot_state(self):
        """Fetches runtime bot state from DB."""
        conn = self.get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bot_state WHERE id = 1;")
            state = cur.fetchone()
        conn.close()
        return state

    def update_bot_state(self, **kwargs):
        """Dynamically updates fields in bot_state table."""
        if not kwargs:
            return
        fields = [f"{k} = %({k})s" for k in kwargs.keys()]
        query = f"UPDATE bot_state SET {', '.join(fields)}, updated_at = NOW() WHERE id = 1;"
        conn = self.get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, kwargs)
            conn.commit()
        conn.close()

    def log_audit(self, level: str, message: str):
        """Records an audit log entry in PostgreSQL."""
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_logs (log_level, message) VALUES (%s, %s);",
                    (level.upper(), message)
                )
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")

    def fetch_klines(self, interval: str, limit: int = 250) -> pd.DataFrame:
        """Fetches kline candle data from Binance REST API and formats into DataFrame."""
        try:
            klines = self.client.get_klines(symbol=self.symbol, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["open"] = df["open"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
        except Exception as e:
            self.log_audit("ERROR", f"Failed to fetch klines for interval {interval}: {e}")
            return pd.DataFrame()

    def compute_indicators(self):
        """Computes technical indicators for 1m, 15m, and 1h timeframes."""
        # 1m Execution Timeframe
        df_1m = self.fetch_klines(Client.KLINE_INTERVAL_1MINUTE, limit=100)
        if df_1m.empty:
            return None

        df_1m["rsi"] = calc_rsi(df_1m["close"], length=14)
        macd_line, signal_line, hist = calc_macd(df_1m["close"], fast=12, slow=26, signal=9)
        df_1m["macd"] = macd_line
        df_1m["macd_signal"] = signal_line
        df_1m["macd_hist"] = hist
        df_1m["vol_ma"] = df_1m["volume"].rolling(window=20).mean()
        df_1m["atr"] = calc_atr(df_1m, length=14)

        # 15m Macro Trend & ADX Filter
        df_15m = self.fetch_klines(Client.KLINE_INTERVAL_15MINUTE, limit=250)
        if not df_15m.empty:
            df_15m["ema200"] = calc_ema(df_15m["close"], length=200)
            df_15m["adx"] = calc_adx(df_15m, length=14)
        
        # 1h Macro Trend Filter
        df_1h = self.fetch_klines(Client.KLINE_INTERVAL_1HOUR, limit=250)
        if not df_1h.empty:
            df_1h["ema200"] = calc_ema(df_1h["close"], length=200)

        # Extract latest closed bar values
        curr_1m = df_1m.iloc[-1]
        prev_1m = df_1m.iloc[-2]

        curr_15m = df_15m.iloc[-1] if not df_15m.empty else None
        curr_1h = df_1h.iloc[-1] if not df_1h.empty else None

        return {
            "1m_curr": curr_1m,
            "1m_prev": prev_1m,
            "15m_curr": curr_15m,
            "1h_curr": curr_1h,
        }

    def check_buy_signal(self, ind: dict) -> bool:
        """
        Pure Code Buy Strategy Logic:
        1. 1m RSI < 30
        2. 1m MACD Bullish Cross
        3. 1m Volume > 1.5 * Volume MA(20)
        4. Macro Filter 1: 15m Price > 15m EMA(200)
        5. Macro Filter 2: 1h Price > 1h EMA(200)
        6. Trend Matrix: 15m ADX > 25
        """
        if not ind:
            return False

        c1m = ind["1m_curr"]
        p1m = ind["1m_prev"]
        c15m = ind["15m_curr"]
        c1h = ind["1h_curr"]

        if c15m is None or c1h is None or pd.isna(c15m.get("ema200")) or pd.isna(c1h.get("ema200")):
            return False

        rsi_condition = c1m["rsi"] < 30.0
        macd_cross = (p1m["macd"] <= p1m["macd_signal"]) and (c1m["macd"] > c1m["macd_signal"])
        volume_spike = c1m["volume"] > (1.5 * c1m["vol_ma"])
        macro_15m_bullish = c15m["close"] > c15m["ema200"]
        macro_1h_bullish = c1h["close"] > c1h["ema200"]
        adx_trending = c15m.get("adx", 0) > 25.0

        is_buy = (
            rsi_condition and
            macd_cross and
            volume_spike and
            macro_15m_bullish and
            macro_1h_bullish and
            adx_trending
        )

        if rsi_condition and macd_cross:
            if not (macro_15m_bullish and macro_1h_bullish):
                self.log_audit("INFO", "BUY signal rejected by Macro 15m/1h EMA(200) Trend Filter.")

        return is_buy

    def execute_buy(self, close_price: float, atr: float, trade_usd_size: float):
        """Executes BUY order and updates PostgreSQL bot state."""
        quantity = round(trade_usd_size / close_price, 6)
        initial_sl = round(close_price - (2.0 * atr), 2)
        initial_tp = round(close_price + (3.0 * atr), 2)

        self.log_audit("INFO", f"EXECUTING BUY ORDER: {quantity} {self.symbol} @ ${close_price:,.2f}")

        # Update bot state in DB
        self.update_bot_state(
            position_open=True,
            side="BUY",
            buy_price=close_price,
            quantity=quantity,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            trailing_sl=initial_sl,
            highest_price=close_price,
            opened_at=datetime.datetime.now(datetime.timezone.utc)
        )

        # Record trade in DB
        conn = self.get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (symbol, side, price, quantity, trade_usd_size, reason)
                VALUES (%s, 'BUY', %s, %s, %s, 'BUY_SIGNAL');
            """, (self.symbol, close_price, quantity, trade_usd_size))
            conn.commit()
        conn.close()

        # Send Telegram Alert
        msg = (
            f"🟢 *BUY ORDER FILLED*\n"
            f" Symbol: `{self.symbol}`\n"
            f" Price: `${close_price:,.2f}`\n"
            f" Quantity: `{quantity}`\n"
            f" Initial SL: `${initial_sl:,.2f}`\n"
            f" Initial TP: `${initial_tp:,.2f}`"
        )
        asyncio.create_task(send_telegram_alert(msg))

    def execute_sell(self, state: dict, exit_price: float, reason: str):
        """Executes SELL order, computes realized PnL, updates balance and circuit breaker stats."""
        buy_price = float(state["buy_price"])
        quantity = float(state["quantity"])
        trade_usd_size = float(state["trade_usd_size"])
        current_balance = float(state["current_balance"])

        pnl = round((exit_price - buy_price) * quantity, 2)
        pnl_pct = round(((exit_price - buy_price) / buy_price) * 100, 2)

        new_balance = round(current_balance + pnl, 2)
        consecutive_losses = state["consecutive_losses"] + 1 if pnl < 0 else 0

        self.log_audit("INFO", f"EXECUTING SELL ORDER: {quantity} {self.symbol} @ ${exit_price:,.2f} | Reason: {reason} | PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")

        # Handle Circuit Breaker (3 consecutive losses -> 2h pause)
        status = "ACTIVE"
        paused_until = None
        if consecutive_losses >= 3:
            status = "CIRCUIT_BREAKER"
            paused_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
            cb_msg = "🚨 *CIRCUIT BREAKER ACTIVATED*: 3 consecutive losses detected! Bot paused for 2 hours."
            self.log_audit("WARNING", cb_msg)
            asyncio.create_task(send_telegram_alert(cb_msg))

        # Check Max Daily Drawdown (>3% loss halts trading)
        start_daily = float(state["start_daily_balance"])
        drawdown_pct = ((start_daily - new_balance) / start_daily) * 100
        if drawdown_pct >= 3.0:
            status = "PAUSED"
            dd_msg = f"🚨 *MAX DAILY DRAWDOWN BREACHED*: Total balance dropped {drawdown_pct:.2f}%. Trading paused."
            self.log_audit("CRITICAL", dd_msg)
            asyncio.create_task(send_telegram_alert(dd_msg))

        # Update bot state in DB
        self.update_bot_state(
            position_open=False,
            side=None,
            buy_price=0.0,
            quantity=0.0,
            initial_sl=0.0,
            initial_tp=0.0,
            trailing_sl=0.0,
            highest_price=0.0,
            opened_at=None,
            current_balance=new_balance,
            consecutive_losses=consecutive_losses,
            status=status,
            paused_until=paused_until
        )

        # Record trade in DB
        conn = self.get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (symbol, side, price, quantity, trade_usd_size, reason, pnl, pnl_pct)
                VALUES (%s, 'SELL', %s, %s, %s, %s, %s, %s);
            """, (self.symbol, exit_price, quantity, trade_usd_size, reason, pnl, pnl_pct))
            conn.commit()
        conn.close()

        # Send Telegram Alert
        emoji = "🔴" if pnl < 0 else "🟢"
        msg = (
            f"{emoji} *SELL ORDER EXECUTED*\n"
            f" Symbol: `{self.symbol}`\n"
            f" Exit Price: `${exit_price:,.2f}`\n"
            f" Reason: `{reason}`\n"
            f" Realized PnL: `${pnl:+,.2f}` (`{pnl_pct:+.2f}%`)\n"
            f" New Balance: `${new_balance:,.2f} USDT`"
        )
        asyncio.create_task(send_telegram_alert(msg))

    def evaluate_position_exit(self, state: dict, ind: dict):
        """Evaluates active position for exit conditions (RSI, Trailing SL, TP/SL, Max Hold Timeout)."""
        close_price = ind["1m_curr"]["close"]
        rsi_1m = ind["1m_curr"]["rsi"]
        buy_price = float(state["buy_price"])
        highest_price = max(float(state["highest_price"]), close_price)
        trailing_sl = float(state["trailing_sl"])
        initial_tp = float(state["initial_tp"])
        initial_sl = float(state["initial_sl"])

        # Check profit percentage
        unrealized_pnl_pct = ((close_price - buy_price) / buy_price) * 100

        # Break-Even & Trailing Stop Engine
        new_trailing_sl = trailing_sl
        if unrealized_pnl_pct >= 1.0:
            break_even = buy_price
            trail_price = round(highest_price * 0.99, 2)
            new_trailing_sl = max(break_even, trail_price)

        if new_trailing_sl != trailing_sl or highest_price != float(state["highest_price"]):
            self.update_bot_state(trailing_sl=new_trailing_sl, highest_price=highest_price)

        # Exit Condition 1: 1m RSI > 70 (Overbought Exit)
        if rsi_1m > 70.0:
            self.execute_sell(state, close_price, "RSI_OVERBOUGHT")
            return

        # Exit Condition 2: Trailing SL Hit
        if close_price <= new_trailing_sl and new_trailing_sl > 0:
            self.execute_sell(state, close_price, "TRAILING_STOP_HIT")
            return

        # Exit Condition 3: Initial Take Profit / Stop Loss Hit
        if close_price >= initial_tp and initial_tp > 0:
            self.execute_sell(state, close_price, "TAKE_PROFIT_HIT")
            return
        if close_price <= initial_sl and initial_sl > 0:
            self.execute_sell(state, close_price, "STOP_LOSS_HIT")
            return

        # Exit Condition 4: Max Hold Time Timeout (45 mins)
        opened_at = state.get("opened_at")
        if opened_at:
            if isinstance(opened_at, str):
                opened_at = datetime.datetime.fromisoformat(opened_at)
            now = datetime.datetime.now(datetime.timezone.utc)
            duration_mins = (now - opened_at).total_seconds() / 60.0
            if duration_mins >= 45.0:
                self.execute_sell(state, close_price, "MAX_HOLD_TIMEOUT")
                return

    def emit_heartbeat(self, close_price: float, ind: dict, position_open: bool, total_balance: float, latency_ms: int):
        """Records diagnostic heartbeat in PostgreSQL bot_heartbeat table."""
        try:
            c1m = ind["1m_curr"] if ind else {}
            c15m = ind["15m_curr"] if ind else {}
            c1h = ind["1h_curr"] if ind else {}

            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bot_heartbeat (
                        close_price, rsi_1m, macd_1m, signal_1m, adx_15m, ema200_15m, ema200_1h,
                        position_open, total_balance, latency_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    close_price,
                    float(c1m.get("rsi", 0)) if not pd.isna(c1m.get("rsi")) else 0,
                    float(c1m.get("macd", 0)) if not pd.isna(c1m.get("macd")) else 0,
                    float(c1m.get("macd_signal", 0)) if not pd.isna(c1m.get("macd_signal")) else 0,
                    float(c15m.get("adx", 0)) if c15m is not None and not pd.isna(c15m.get("adx")) else 0,
                    float(c15m.get("ema200", 0)) if c15m is not None and not pd.isna(c15m.get("ema200")) else 0,
                    float(c1h.get("ema200", 0)) if c1h is not None and not pd.isna(c1h.get("ema200")) else 0,
                    position_open,
                    total_balance,
                    latency_ms
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record heartbeat: {e}")

    async def start(self):
        """Main async runtime loop executing sub-second strategy cycle."""
        self.log_audit("INFO", f"Starting Trading Engine Loop for {self.symbol}...")
        while True:
            t0 = time.time()
            try:
                state = self.load_bot_state()
                status = state["status"]
                
                # Check Circuit Breaker expiration
                if status == "CIRCUIT_BREAKER":
                    paused_until = state.get("paused_until")
                    if paused_until and datetime.datetime.now(datetime.timezone.utc) >= paused_until:
                        self.update_bot_state(status="ACTIVE", consecutive_losses=0, paused_until=None)
                        self.log_audit("INFO", "Circuit Breaker cooldown expired. Trading reactivated.")
                        status = "ACTIVE"

                ind = self.compute_indicators()
                latency_ms = int((time.time() - t0) * 1000)

                if ind and ind["1m_curr"] is not None:
                    close_price = float(ind["1m_curr"]["close"])
                    atr = float(ind["1m_curr"]["atr"]) if not pd.isna(ind["1m_curr"]["atr"]) else (close_price * 0.01)
                    position_open = state["position_open"]
                    total_balance = float(state["current_balance"])

                    # Emit diagnostic heartbeat
                    self.emit_heartbeat(close_price, ind, position_open, total_balance, latency_ms)

                    if status == "ACTIVE":
                        if not position_open:
                            if self.check_buy_signal(ind):
                                self.execute_buy(close_price, atr, float(state["trade_usd_size"]))
                        else:
                            self.evaluate_position_exit(state, ind)

            except Exception as e:
                self.log_audit("ERROR", f"Unhandled error in main bot loop: {e}")
                await asyncio.sleep(5)

            # Execution sleep cycle (2 seconds)
            await asyncio.sleep(2)

if __name__ == "__main__":
    bot = AlgorithmicTradingBot()
    asyncio.run(bot.start())
