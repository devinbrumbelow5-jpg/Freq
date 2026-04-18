import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
import logging
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FreqDB:
    _pool = None
    _lock = threading.Lock()

    @classmethod
    def init_pool(cls):
        with cls._lock:
            if cls._pool is None:
                cls._pool = ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    host="localhost",
                    database="freqdb",
                    user="frequser",
                    password="freqpass"
                )
                logger.info("✅ PostgreSQL ThreadedConnectionPool initialized (max 20 connections)")

    def __init__(self):
        self.init_pool()

    def get_conn(self):
        return self._pool.getconn()

    def put_conn(self, conn):
        self._pool.putconn(conn)

    def log_trade(self, bot_id: str, pair: str, side: str, qty: float, price: float, pnl: float = 0.0):
        conn = self.get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                INSERT INTO trades (bot_id, pair, side, qty, price, pnl)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (bot_id, pair, side, qty, price, pnl))
            conn.commit()
            logger.info(f"TRADE LOGGED | {bot_id} | {side} {qty} {pair} @ {price} | PnL {pnl}")
        finally:
            cur.close()
            self.put_conn(conn)

    def update_position(self, bot_id: str, pair: str, side: str, qty: float, entry_price: float, current_price: float = None):
        """Update position with net-of-fees unrealized PnL"""
        conn = self.get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Fee and slippage constants
            TAKER_FEE = 0.0026
            SLIPPAGE = 0.0005
            SINGLE_LEG_COST = TAKER_FEE + SLIPPAGE  # 0.31%
            
            # Calculate gross unrealized PnL
            unrealized_gross = 0.0
            if current_price and qty != 0:
                unrealized_gross = (current_price - entry_price) * qty if side.upper() == "BUY" else (entry_price - current_price) * qty
            
            # Apply fee adjustment for unrealized PnL
            # For unrealized, estimate net by accounting for fees on both legs
            if qty != 0:
                entry_fees = entry_price * qty * SINGLE_LEG_COST
                estimated_exit_fees = current_price * qty * SINGLE_LEG_COST
                unrealized = unrealized_gross - entry_fees - estimated_exit_fees
            else:
                unrealized = 0.0

            cur.execute("""
                INSERT INTO positions (bot_id, pair, side, qty, entry_price, current_price, unrealized_pnl)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bot_id, pair) DO UPDATE
                SET qty = EXCLUDED.qty,
                    entry_price = EXCLUDED.entry_price,
                    current_price = EXCLUDED.current_price,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    timestamp = CURRENT_TIMESTAMP
            """, (bot_id, pair, side, qty, entry_price, current_price, unrealized))
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    def get_active_positions(self, bot_id: str = None):
        conn = self.get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if bot_id:
                cur.execute("SELECT * FROM positions WHERE bot_id = %s AND qty != 0", (bot_id,))
            else:
                cur.execute("SELECT * FROM positions WHERE qty != 0")
            return cur.fetchall()
        finally:
            cur.close()
            self.put_conn(conn)

    def log_bot_event(self, bot_id: str, level: str, message: str):
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO bot_logs (bot_id, level, message) VALUES (%s, %s, %s)",
                        (bot_id, level, message))
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    def store_balance(self, currency: str, balance: float):
        """Store account balance in database"""
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            # Create balances table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    currency VARCHAR(10) PRIMARY KEY,
                    balance DECIMAL(18, 8),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                INSERT INTO balances (currency, balance, timestamp)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (currency) DO UPDATE
                SET balance = EXCLUDED.balance,
                    timestamp = CURRENT_TIMESTAMP
            """, (currency, balance))
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    def get_latest_balance(self, currency: str = 'USDC'):
        """Get latest balance for a currency"""
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT balance FROM balances 
                WHERE currency = %s 
                ORDER BY timestamp DESC LIMIT 1
            """, (currency,))
            result = cur.fetchone()
            return float(result[0]) if result else 1000.0
        except:
            return 1000.0
        finally:
            cur.close()
            self.put_conn(conn)

    def close(self):
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL pool closed")
