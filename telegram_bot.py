import asyncio
import logging
import datetime
import urllib.request
import urllib.parse
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DATABASE_URL

logger = logging.getLogger("TelegramEngine")

def send_telegram_sync(message: str):
    """Synchronous HTTP post to Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info(f"[Telegram Disabled/Unconfigured] Alert suppressed: {message[:100]}...")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False

async def send_telegram_alert(message: str):
    """Async wrapper for non-blocking Telegram notifications."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_telegram_sync, message)

def generate_daily_summary_report() -> str:
    """Queries PostgreSQL database for past 24h trade stats and formats markdown summary."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            # Query trades executed in past 24h
            cur.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as winning_trades,
                    COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as losing_trades,
                    COALESCE(SUM(pnl), 0.0) as net_pnl
                FROM trades 
                WHERE created_at >= NOW() - INTERVAL '24 hours' AND side = 'SELL';
            """)
            stats = cur.fetchone()
            
            # Query bot balance
            cur.execute("SELECT current_balance, start_daily_balance FROM bot_state WHERE id = 1;")
            state = cur.fetchone()
        conn.close()

        total = stats["total_trades"] if stats else 0
        wins = stats["winning_trades"] if stats else 0
        losses = stats["losing_trades"] if stats else 0
        net_pnl = float(stats["net_pnl"]) if stats else 0.0
        
        win_rate = (wins / total * 100) if total > 0 else 0.0
        
        current_bal = float(state["current_balance"]) if state else 1000.0
        start_bal = float(state["start_daily_balance"]) if state else 1000.0
        pnl_pct = ((current_bal - start_bal) / start_bal * 100) if start_bal > 0 else 0.0

        summary = (
            "📊 *24-HOUR DAILY TRADING PERFORMANCE REVIEW*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Date*: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"💰 *Current Balance*: `${current_bal:,.2f} USDT`\n"
            f"📈 *24h Net PnL*: `${net_pnl:+,.2f} USD` (`{pnl_pct:+.2f}%`)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 *Total Executed Trades*: `{total}`\n"
            f"✅ *Winning Trades*: `{wins}`\n"
            f"❌ *Losing Trades*: `{losses}`\n"
            f"🎯 *Daily Win Rate*: `{win_rate:.1f}%`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 *Engine Status*: `ACTIVE & OPERATIONAL`"
        )
        return summary
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        return f"⚠️ Error generating daily trade summary: {e}"

async def daily_summary_scheduler():
    """Background task triggering 24h trade review at 00:00 UTC."""
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        # Calculate seconds until next 00:00 UTC
        next_run = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        sleep_seconds = (next_run - now).total_seconds()
        
        logger.info(f"Daily summary scheduler sleeping for {sleep_seconds/3600:.2f} hours until 00:00 UTC.")
        await asyncio.sleep(sleep_seconds)
        
        # Send daily summary
        report = generate_daily_summary_report()
        await send_telegram_alert(report)

if __name__ == "__main__":
    print("Testing Daily Summary Generation:")
    print(generate_daily_summary_report())
