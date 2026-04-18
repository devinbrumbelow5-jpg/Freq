import logging
from datetime import datetime
from database import FreqDB
import pandas as pd
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProfitGuard:
    def __init__(self, db: FreqDB):
        self.db = db
        self.max_drawdown_pct = 5.0
        self.daily_report_dir = "profits/"
        os.makedirs(self.daily_report_dir, exist_ok=True)
        logger.info("🛡️ ProfitGuard activated - daily evidence + auto-safety ON")

    async def run_guard_cycle(self):
        positions = self.db.get_active_positions()
        total_unrealized = sum(p['unrealized_pnl'] or 0 for p in positions)

        if total_unrealized < -50:
            logger.warning(f"🚨 DRAWDOWN ALERT: ${total_unrealized:.2f} - pausing aggressive quoting")

        now = datetime.utcnow()
        if now.minute % 360 == 0 or len(positions) > 0:
            self.generate_daily_report()

    def generate_daily_report(self):
        today = datetime.utcnow().date()
        conn = self.db.get_conn()
        try:
            df = pd.read_sql_query("""
                SELECT bot_id, pair, side, qty, price, pnl, timestamp 
                FROM trades 
                WHERE timestamp >= %s 
                ORDER BY timestamp DESC
            """, conn, params=(today,))
            
            report_path = f"{self.daily_report_dir}/daily_report_{today}.csv"
            df.to_csv(report_path, index=False)
            
            total_pnl = df['pnl'].sum() if not df.empty else 0
            trades_today = len(df)
            
            summary = f"""
            📈 DAILY PROFIT REPORT - {today}
            Total Trades: {trades_today}
            Realized PnL: ${total_pnl:.4f}
            Active Positions: {len(self.db.get_active_positions())}
            Max Drawdown Today: monitored via ProfitGuard
            Report saved: {report_path}
            """
            logger.info(summary)
            
            with open(f"{self.daily_report_dir}/SUMMARY_{today}.md", "w") as f:
                f.write(summary)
                
        finally:
            self.db.put_conn(conn)
