# Pure Python Algorithmic Trading Platform (Enterprise Edition)

Enterprise-grade, high-speed Pure Python Algorithmic Trading Platform combined with PostgreSQL (Supabase) persistence and a modern, high-precision Real-Time Glassmorphic Control Terminal UI (React / Tailwind / Node.js). 100% code-driven without external AI API costs or latency overheads.

---

## Architecture Setup (100% FREE Deployment Stack)

| Component | Platform | Cost |
| :--- | :--- | :--- |
| **Database** | Supabase (PostgreSQL) | $0.00 (Free Tier) |
| **Control Dashboard UI** | Vercel (React Frontend) | $0.00 (Free Tier) |
| **24/7 Trading Bot Engine** | Render.com (Python Worker) | $0.00 (750 Free Hours/mo) |

---

## 1. Supabase Database Setup

1. Log into your [Supabase Console](https://supabase.com/).
2. Create a new project.
3. Open **SQL Editor** from the left sidebar.
4. Copy the entire contents of `schema.sql` and run it to create `bot_state`, `trades`, `bot_heartbeat`, and `audit_logs` tables.
5. Go to **Project Settings** -> **Database** -> **Connection String** -> Select **URI** (or Session Pooler).
6. Copy your database connection string:
   ```env
   SUPABASE_DB_URL="postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
   ```

---

## 2. Render.com (24/7 Python Trading Bot) Setup

1. Push this repository to your GitHub account.
2. Log into [Render.com](https://render.com/).
3. Click **New +** -> Select **Background Worker** (or Web Service).
4. Connect your GitHub repository.
5. Set Environment to **Python 3**.
6. Set Build Command: `pip install -r requirements.txt`
7. Set Start Command: `python bot.py`
8. Add Environment Variables in Render Dashboard:
   - `TRADING_MODE` = `TESTNET` (or `PRODUCTION`)
   - `ENABLE_REAL_MONEY_TRADING` = `false` (set `true` for live production)
   - `BINANCE_API_KEY` = your Binance API Key
   - `BINANCE_API_SECRET` = your Binance API Secret
   - `DATABASE_URL` = your Supabase Connection URI
   - `TELEGRAM_BOT_TOKEN` = your Telegram Bot token
   - `TELEGRAM_CHAT_ID` = your Telegram Chat ID
9. Click **Deploy**. Render will run `bot.py` 24/7 in the background for free!

---

## 3. Vercel (React Control Dashboard UI) Setup

1. Log into [Vercel](https://vercel.com/).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository.
4. Set Root Directory to `dashboard/frontend`.
5. Framework Preset: **Vite**.
6. Click **Deploy**.
7. Vercel will host your modern glassmorphic trading terminal on a fast global CDN!

---

## 4. Local Machine Quickstart (Docker Compose)

To run the entire platform locally on your own Windows computer:

```bash
# 1. Clone the project and navigate into directory
cd algo_trading_platform

# 2. Copy environment file and configure keys
cp .env.example .env

# 3. Build and launch all services via Docker
docker-compose up --build -d
```

Open your browser at `http://localhost:3000` to view the Real-Time Control Terminal!

---

## Triple-Lock Safety Verification

1. **Lock 1 (URI Check)**: Automatically forces `https://testnet.binance.vision` when `TRADING_MODE=TESTNET`.
2. **Lock 2 (Real Money Guard)**: If `TRADING_MODE=PRODUCTION`, execution is blocked unless `ENABLE_REAL_MONEY_TRADING=true`.
3. **Lock 3 (API Key Permission Guard)**: The bot automatically queries Binance API permissions upon startup and will immediately shut down if withdrawal permissions are enabled.

---

## Summary of Completed Files

- `schema.sql` - PostgreSQL migration script.
- `config.py` - Configuration and Triple-Lock Safety Validator.
- `bot.py` - Main Python multi-timeframe strategy engine.
- `telegram_bot.py` - Async Telegram alerts and 24h daily summary scheduler.
- `dashboard/backend/server.js` - Node.js Express & Socket.IO server.
- `dashboard/frontend/src/App.jsx` - React glassmorphic trading terminal UI.
- `docker-compose.yml` - Multi-container setup.
