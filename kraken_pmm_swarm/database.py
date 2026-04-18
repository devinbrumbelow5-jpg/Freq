"""
Simplified Database module for Kraken PMM Swarm.
Uses sync sqlite3 with asyncio.to_thread for async compatibility.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio


class DatabaseManager:
    """Async-compatible SQLite database manager."""
    
    def __init__(self, db_path: str = "./pmm_swarm.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
    
    async def connect(self):
        """Initialize database connection and tables."""
        def _connect():
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn
        
        self._conn = await asyncio.to_thread(_connect)
        await self._create_tables()
    
    async def close(self):
        """Close database connection."""
        if self._conn:
            def _close():
                self._conn.close()
            await asyncio.to_thread(_close)
            self._conn = None
    
    async def _create_tables(self):
        """Create all required tables."""
        def _create():
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    order_id TEXT UNIQUE NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    filled_amount REAL DEFAULT 0.0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_orders_bot ON orders(bot_id);
                CREATE INDEX IF NOT EXISTS idx_orders_pair ON orders(pair);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                
                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    fill_id TEXT UNIQUE NOT NULL,
                    bot_id TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL DEFAULT 0.0,
                    fee_currency TEXT,
                    filled_at TEXT NOT NULL,
                    pnl_realized REAL DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS idx_fills_bot ON fills(bot_id);
                CREATE INDEX IF NOT EXISTS idx_fills_pair ON fills(pair);
                CREATE INDEX IF NOT EXISTS idx_fills_time ON fills(filled_at);
                
                CREATE TABLE IF NOT EXISTS balances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    available REAL DEFAULT 0.0,
                    reserved REAL DEFAULT 0.0,
                    total REAL DEFAULT 0.0,
                    usd_value REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(bot_id, currency)
                );
                
                CREATE TABLE IF NOT EXISTS pnl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    date TEXT NOT NULL,
                    realized_pnl REAL DEFAULT 0.0,
                    unrealized_pnl REAL DEFAULT 0.0,
                    fees_paid REAL DEFAULT 0.0,
                    trade_count INTEGER DEFAULT 0,
                    volume REAL DEFAULT 0.0,
                    UNIQUE(bot_id, pair, date)
                );
                CREATE INDEX IF NOT EXISTS idx_pnl_bot_date ON pnl(bot_id, date);
                
                CREATE TABLE IF NOT EXISTS bot_status (
                    bot_id TEXT PRIMARY KEY,
                    pair TEXT NOT NULL,
                    is_running INTEGER DEFAULT 0,
                    current_bid REAL,
                    current_ask REAL,
                    mid_price REAL,
                    spread_bps REAL,
                    position_size REAL DEFAULT 0.0,
                    position_value REAL DEFAULT 0.0,
                    inventory_skew REAL DEFAULT 0.0,
                    orders_open INTEGER DEFAULT 0,
                    last_update TEXT NOT NULL,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT
                );
            """)
            self._conn.commit()
        
        await asyncio.to_thread(_create)
    
    async def insert_order(self, bot_id: str, pair: str, order_id: str, 
                          side: str, order_type: str, price: float, 
                          amount: float, metadata: Optional[Dict] = None) -> bool:
        """Insert a new order."""
        def _insert():
            try:
                now = datetime.utcnow().isoformat()
                self._conn.execute("""
                    INSERT INTO orders (bot_id, pair, order_id, side, order_type, 
                                       price, amount, status, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
                """, (bot_id, pair, order_id, side, order_type, price, amount, 
                      now, now, json.dumps(metadata) if metadata else None))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def update_order_status(self, order_id: str, status: str, 
                                  filled_amount: Optional[float] = None) -> bool:
        """Update order status."""
        def _update():
            try:
                now = datetime.utcnow().isoformat()
                if filled_amount is not None:
                    self._conn.execute("""
                        UPDATE orders SET status = ?, filled_amount = ?, updated_at = ?
                        WHERE order_id = ?
                    """, (status, filled_amount, now, order_id))
                else:
                    self._conn.execute("""
                        UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?
                    """, (status, now, order_id))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_update)
    
    async def insert_fill(self, order_id: str, fill_id: str, bot_id: str, 
                         pair: str, side: str, price: float, amount: float,
                         fee: float = 0.0, fee_currency: str = "USDT",
                         pnl_realized: float = 0.0) -> bool:
        """Record a fill."""
        def _insert():
            try:
                now = datetime.utcnow().isoformat()
                self._conn.execute("""
                    INSERT INTO fills (order_id, fill_id, bot_id, pair, side, price, 
                                      amount, fee, fee_currency, filled_at, pnl_realized)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, fill_id, bot_id, pair, side, price, amount, 
                      fee, fee_currency, now, pnl_realized))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def update_balance(self, bot_id: str, currency: str, available: float,
                            reserved: float = 0.0, total: Optional[float] = None,
                            usd_value: float = 0.0) -> bool:
        """Update balance."""
        def _update():
            try:
                now = datetime.utcnow().isoformat()
                if total is None:
                    total = available + reserved
                self._conn.execute("""
                    INSERT INTO balances (bot_id, currency, available, reserved, total, usd_value, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id, currency) DO UPDATE SET
                        available = excluded.available,
                        reserved = excluded.reserved,
                        total = excluded.total,
                        usd_value = excluded.usd_value,
                        updated_at = excluded.updated_at
                """, (bot_id, currency, available, reserved, total, usd_value, now))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_update)
    
    async def update_pnl(self, bot_id: str, pair: str, date: str,
                        realized_pnl: Optional[float] = None,
                        unrealized_pnl: Optional[float] = None,
                        fees_paid: Optional[float] = None,
                        trade_count: Optional[int] = None,
                        volume: Optional[float] = None) -> bool:
        """Update P&L."""
        def _update():
            try:
                self._conn.execute("""
                    INSERT INTO pnl (bot_id, pair, date, realized_pnl, unrealized_pnl, 
                                   fees_paid, trade_count, volume)
                    VALUES (?, ?, ?, COALESCE(?, 0), COALESCE(?, 0), 
                            COALESCE(?, 0), COALESCE(?, 0), COALESCE(?, 0))
                    ON CONFLICT(bot_id, pair, date) DO UPDATE SET
                        realized_pnl = realized_pnl + COALESCE(excluded.realized_pnl, 0),
                        unrealized_pnl = COALESCE(excluded.unrealized_pnl, unrealized_pnl),
                        fees_paid = fees_paid + COALESCE(excluded.fees_paid, 0),
                        trade_count = trade_count + COALESCE(excluded.trade_count, 0),
                        volume = volume + COALESCE(excluded.volume, 0)
                """, (bot_id, pair, date, realized_pnl, unrealized_pnl, 
                      fees_paid, trade_count, volume))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_update)
    
    async def update_bot_status(self, bot_id: str, pair: str, is_running: bool,
                              current_bid: Optional[float] = None,
                              current_ask: Optional[float] = None,
                              mid_price: Optional[float] = None,
                              spread_bps: Optional[float] = None,
                              position_size: Optional[float] = None,
                              position_value: Optional[float] = None,
                              inventory_skew: Optional[float] = None,
                              orders_open: Optional[int] = None,
                              error_count: Optional[int] = None,
                              last_error: Optional[str] = None) -> bool:
        """Update bot status."""
        def _update():
            try:
                now = datetime.utcnow().isoformat()
                self._conn.execute("""
                    INSERT INTO bot_status (bot_id, pair, is_running, current_bid, current_ask,
                                          mid_price, spread_bps, position_size, position_value,
                                          inventory_skew, orders_open, last_update, error_count, last_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        pair = excluded.pair,
                        is_running = excluded.is_running,
                        current_bid = COALESCE(excluded.current_bid, current_bid),
                        current_ask = COALESCE(excluded.current_ask, current_ask),
                        mid_price = COALESCE(excluded.mid_price, mid_price),
                        spread_bps = COALESCE(excluded.spread_bps, spread_bps),
                        position_size = COALESCE(excluded.position_size, position_size),
                        position_value = COALESCE(excluded.position_value, position_value),
                        inventory_skew = COALESCE(excluded.inventory_skew, inventory_skew),
                        orders_open = COALESCE(excluded.orders_open, orders_open),
                        last_update = excluded.last_update,
                        error_count = COALESCE(excluded.error_count, error_count),
                        last_error = COALESCE(excluded.last_error, last_error)
                """, (bot_id, pair, int(is_running), current_bid, current_ask, mid_price,
                      spread_bps, position_size, position_value, inventory_skew, orders_open,
                      now, error_count, last_error))
                self._conn.commit()
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_update)
    
    async def get_open_orders(self, bot_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders."""
        def _get():
            if bot_id:
                cursor = self._conn.execute(
                    "SELECT * FROM orders WHERE bot_id = ? AND status = 'open'",
                    (bot_id,)
                )
            else:
                cursor = self._conn.execute("SELECT * FROM orders WHERE status = 'open'")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        return await asyncio.to_thread(_get)
    
    async def get_fills(self, bot_id: Optional[str] = None, 
                       since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get fills."""
        def _get():
            query = "SELECT * FROM fills WHERE 1=1"
            params = []
            if bot_id:
                query += " AND bot_id = ?"
                params.append(bot_id)
            if since:
                query += " AND filled_at > ?"
                params.append(since)
            query += " ORDER BY filled_at DESC"
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        return await asyncio.to_thread(_get)
    
    async def get_balances(self, bot_id: str) -> Dict[str, Dict[str, Any]]:
        """Get balances."""
        def _get():
            cursor = self._conn.execute(
                "SELECT * FROM balances WHERE bot_id = ?",
                (bot_id,)
            )
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                row_dict = dict(row)
                result[row_dict['currency']] = row_dict
            return result
        
        return await asyncio.to_thread(_get)
    
    async def get_pnl_summary(self, bot_id: Optional[str] = None,
                             since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get P&L summary."""
        def _get():
            query = """
                SELECT bot_id, pair, SUM(realized_pnl) as total_realized,
                       SUM(unrealized_pnl) as total_unrealized,
                       SUM(fees_paid) as total_fees,
                       SUM(trade_count) as total_trades,
                       SUM(volume) as total_volume
                FROM pnl WHERE 1=1
            """
            params = []
            if bot_id:
                query += " AND bot_id = ?"
                params.append(bot_id)
            if since:
                query += " AND date >= ?"
                params.append(since)
            query += " GROUP BY bot_id, pair"
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        return await asyncio.to_thread(_get)
    
    async def get_all_bot_status(self) -> List[Dict[str, Any]]:
        """Get all bot status."""
        def _get():
            cursor = self._conn.execute("SELECT * FROM bot_status")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        return await asyncio.to_thread(_get)
    
    async def backup(self, backup_path: Optional[str] = None):
        """Backup database."""
        def _backup():
            if backup_path is None:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                path = self.db_path.parent / f"pmm_swarm_backup_{timestamp}.db"
            else:
                path = Path(backup_path)
            self._conn.execute(f"VACUUM INTO '{path}'")
        
        await asyncio.to_thread(_backup)
