-- =========================================================
-- PURE PYTHON ALGORITHMIC TRADING PLATFORM SCHEMA (SUPABASE/POSTGRESQL)
-- =========================================================

-- 1. Bot State Table (Single-row table tracking current runtime status & active position)
CREATE TABLE IF NOT EXISTS bot_state (
    id INT PRIMARY KEY DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, PAUSED, CIRCUIT_BREAKER
    position_open BOOLEAN NOT NULL DEFAULT FALSE,
    symbol VARCHAR(20) DEFAULT 'BTCUSDT',
    side VARCHAR(10) DEFAULT NULL, -- BUY or SELL
    buy_price NUMERIC(18, 8) DEFAULT 0.0,
    quantity NUMERIC(18, 8) DEFAULT 0.0,
    trade_usd_size NUMERIC(18, 2) DEFAULT 10.00,
    initial_sl NUMERIC(18, 8) DEFAULT 0.0,
    initial_tp NUMERIC(18, 8) DEFAULT 0.0,
    trailing_sl NUMERIC(18, 8) DEFAULT 0.0,
    highest_price NUMERIC(18, 8) DEFAULT 0.0,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    current_balance NUMERIC(18, 2) DEFAULT 1000.00,
    start_daily_balance NUMERIC(18, 2) DEFAULT 1000.00,
    consecutive_losses INT DEFAULT 0,
    paused_until TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT single_row CHECK (id = 1)
);

-- Seed initial bot_state row if not exists
INSERT INTO bot_state (id, status, position_open, current_balance, start_daily_balance)
VALUES (1, 'ACTIVE', FALSE, 1000.00, 1000.00)
ON CONFLICT (id) DO NOTHING;

-- 2. Trades Table (Complete history of executed trades)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- BUY / SELL
    price NUMERIC(18, 8) NOT NULL,
    quantity NUMERIC(18, 8) NOT NULL,
    trade_usd_size NUMERIC(18, 2) NOT NULL,
    rsi NUMERIC(8, 2),
    macd NUMERIC(12, 6),
    signal_line NUMERIC(12, 6),
    adx NUMERIC(8, 2),
    atr NUMERIC(12, 6),
    reason VARCHAR(100) NOT NULL, -- BUY_SIGNAL, TP1_HIT, TP2_HIT, TRAILING_SL_HIT, PANIC, MAX_HOLD_TIMEOUT
    pnl NUMERIC(18, 2) DEFAULT 0.00,
    pnl_pct NUMERIC(8, 4) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for high-speed PnL aggregation & queries
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at);

-- 3. Bot Heartbeat Table (Diagnostics, live indicator telemetry, and latency)
CREATE TABLE IF NOT EXISTS bot_heartbeat (
    id SERIAL PRIMARY KEY,
    close_price NUMERIC(18, 8) NOT NULL,
    rsi_1m NUMERIC(8, 2),
    macd_1m NUMERIC(12, 6),
    signal_1m NUMERIC(12, 6),
    adx_15m NUMERIC(8, 2),
    ema200_15m NUMERIC(18, 8),
    ema200_1h NUMERIC(18, 8),
    position_open BOOLEAN NOT NULL,
    total_balance NUMERIC(18, 2) NOT NULL,
    latency_ms INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index to optimize live charts & cleanup operations
CREATE INDEX IF NOT EXISTS idx_heartbeat_created_at ON bot_heartbeat(created_at);

-- 4. Audit Logs Table (System alerts, error tracebacks, and control actions)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR, CRITICAL, PANIC
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);
