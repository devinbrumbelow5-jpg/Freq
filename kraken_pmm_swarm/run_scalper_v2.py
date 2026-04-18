#!/usr/bin/env python3
"""
Mean Reversion Scalper v2.0 - For Choppy Markets
- Bollinger Band entries (price extremes)
- Fixed position sizing with proper fractional tracking
- Smaller trades: $200-300 per position
- Target: 0.3-0.5% per trade, stop: 0.5%
"""

import asyncio
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager


@dataclass
class ScalperConfig:
    pair: str
    order_size_usd: float = 250  # Smaller = more flexibility
    bb_period: int = 15  # Faster response
    bb_std: float = 1.8  # Tighter bands = more signals
    take_profit_pct: float = 0.25  # REDUCED: 25bps target for faster exits
    stop_loss_pct: float = 0.4   # REDUCED: 40bps stop to cut losses faster
    max_positions: int = 1  # REDUCED: Only 1 position per pair to limit exposure
    max_total_positions: int = 3  # NEW: Max 3 total across all pairs
    entry_cooldown_seconds: int = 300  # NEW: 5min cooldown between entries


class MeanReversionScalper:
    """Bollinger Band mean reversion with proper position tracking."""
    
    def __init__(self, bot_id: str, config: ScalperConfig, client: CoinbasePaperClient, db: DatabaseManager, global_state=None):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = db
        self.global_state = global_state  # Shared state for position limits
        
        self.prices = deque(maxlen=config.bb_period + 5)
        self.is_running = False
        self._task = None
        
        # Position tracking - track entry prices for multiple positions
        self.positions = []  # List of (entry_price, amount) tuples
        self.total_pnl = 0.0
        self.wins = 0
        self.losses = 0
        self.trades = 0
        self.last_entry_time = 0  # Cooldown tracking
        
        self.client.on_fill = self._on_fill
    
    def _calc_bands(self):
        """Calculate Bollinger Bands."""
        if len(self.prices) < self.config.bb_period:
            return None
        prices = list(self.prices)[-self.config.bb_period:]
        sma = statistics.mean(prices)
        std = statistics.stdev(prices) if len(prices) > 1 else 0
        return {
            'upper': sma + std * self.config.bb_std,
            'middle': sma,
            'lower': sma - std * self.config.bb_std
        }
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        
        # Sync positions from database on startup
        await self._sync_positions_from_db()
        
        self._task = asyncio.create_task(self._loop())
    
    async def _sync_positions_from_db(self):
        """Sync internal position tracker with database fills."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # Get all fills for this bot's pair
            cursor.execute("""
                SELECT side, price, amount, filled_at 
                FROM fills 
                WHERE bot_id = ? AND pair = ?
                ORDER BY filled_at ASC
            """, (self.bot_id, self.config.pair))
            
            fills = cursor.fetchall()
            conn.close()
            
            # Rebuild position state (FIFO matching)
            buys = []
            for side, price, amount, ts in fills:
                if side == 'buy':
                    buys.append([price, amount])
                else:  # sell
                    # Match to earliest buy
                    sell_amt = amount
                    while sell_amt > 0.00001 and buys:
                        entry_price, buy_amt = buys[0]
                        match_amt = min(sell_amt, buy_amt)
                        sell_amt -= match_amt
                        buys[0][1] -= match_amt
                        if buys[0][1] < 0.00001:
                            buys.pop(0)
            
            # Set positions to remaining unmatched buys
            self.positions = [(p, a) for p, a in buys if a > 0.00001]
            
            if self.positions:
                total = sum(a for _, a in self.positions)
                print(f"📊 {self.bot_id}: Synced {len(self.positions)} positions ({total:.6f} {self.config.pair.split('/')[0]})")
            
        except Exception as e:
            print(f"⚠️ {self.bot_id}: Position sync failed: {e}")
    
    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _loop(self):
        """Main trading loop."""
        while self.is_running:
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(0.5)
                    continue
                
                price = ob.mid_price
                self.prices.append(price)
                
                bands = self._calc_bands()
                if not bands:
                    await asyncio.sleep(0.5)
                    continue
                
                # Get current position for this pair
                current_pos = self.client.get_position(self.config.pair)
                
                # Check exits first (manage existing positions)
                if self.positions:
                    for i, (entry_price, amount) in enumerate(list(self.positions)):
                        pnl_pct = (price - entry_price) / entry_price * 100
                        
                        # Debug: Log PnL check
                        if i == 0:  # Only log first position to avoid spam
                            print(f"📊 {self.bot_id}: Price ${price:.2f} | Entry ${entry_price:.2f} | PnL {pnl_pct:.2f}% | TP {self.config.take_profit_pct}% | SL {self.config.stop_loss_pct}%")
                        
                        # Take profit
                        if pnl_pct >= self.config.take_profit_pct:
                            print(f"🎯 {self.bot_id}: TAKE PROFIT TRIGGERED {pnl_pct:.2f}% >= {self.config.take_profit_pct}%")
                            success = await self._exit_position(price, amount, "take_profit", pnl_pct)
                            if success:
                                self.positions.pop(i)
                                if self.global_state:
                                    self.global_state['total_open_positions'] = max(0, self.global_state.get('total_open_positions', 0) - 1)
                            break
                        
                        # Stop loss
                        elif pnl_pct <= -self.config.stop_loss_pct:
                            print(f"🛑 {self.bot_id}: STOP LOSS TRIGGERED {pnl_pct:.2f}% <= -{self.config.stop_loss_pct}%")
                            success = await self._exit_position(price, amount, "stop_loss", pnl_pct)
                            if success:
                                self.positions.pop(i)
                                if self.global_state:
                                    self.global_state['total_open_positions'] = max(0, self.global_state.get('total_open_positions', 0) - 1)
                            break
                
                # Entry logic (only if under max positions AND global limits)
                can_enter = len(self.positions) < self.config.max_positions
                
                # Check global position limit
                if can_enter and self.global_state:
                    total_open = self.global_state.get('total_open_positions', 0)
                    can_enter = total_open < self.config.max_total_positions
                
                # Check cooldown
                if can_enter:
                    import time
                    time_since_entry = time.time() - self.last_entry_time
                    can_enter = time_since_entry > self.config.entry_cooldown_seconds
                
                if can_enter:
                    base, quote = self.config.pair.split('/')
                    usd_bal = self.client.get_balance(quote).get('available', 0)
                    
                    # Buy signal: price below lower band
                    if price < bands['lower'] and usd_bal >= self.config.order_size_usd * 1.05:
                        amount = self.config.order_size_usd / price
                        order = await self.client.create_limit_order(
                            self.bot_id, self.config.pair, 'buy',
                            round(price, 2), round(amount, 6),
                            {'signal': 'bb_buy', 'lower': bands['lower'], 'mid': bands['middle']}
                        )
                        if order:
                            self.positions.append((price, amount))
                            self.last_entry_time = time.time()
                            # Update global state
                            if self.global_state:
                                self.global_state['total_open_positions'] = self.global_state.get('total_open_positions', 0) + 1
                            print(f"🟢 {self.bot_id}: BUY ${self.config.order_size_usd:.0f} @ ${price:.2f} "
                                  f"(band: ${bands['lower']:.2f}) [Global: {self.global_state.get('total_open_positions', 0) if self.global_state else 'N/A'}]")
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(2)
    
    async def _exit_position(self, price, amount, reason, pnl_pct):
        """Exit a position with proper sizing. Returns True if exit successful."""
        base, quote = self.config.pair.split('/')
        base_bal = self.client.get_balance(base).get('available', 0)
        
        # Sell what we actually have, not what we think we have
        sell_amount = min(amount, base_bal * 0.99)  # 1% buffer
        
        if sell_amount > 0.0001:  # Minimum size
            print(f"  → Placing sell order: {sell_amount:.6f} {base} @ ${price:.2f}")
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'sell',
                round(price, 2), round(sell_amount, 6),
                {'exit': reason, 'pnl_pct': pnl_pct}
            )
            
            if order:
                self.total_pnl += pnl_pct
                self.trades += 1
                if pnl_pct > 0:
                    self.wins += 1
                else:
                    self.losses += 1
                
                emoji = "✅" if pnl_pct > 0 else "❌"
                print(f"{emoji} {self.bot_id}: {reason.upper()} {pnl_pct:+.2f}% | "
                      f"Total: {self.total_pnl:+.2f}% | WR: {self.wins}/{self.trades}")
                return True
            else:
                print(f"❌ {self.bot_id}: Sell order failed")
                return False
        else:
            print(f"⚠️ {self.bot_id}: Insufficient balance to sell {amount:.6f} {base} (have {base_bal:.6f})")
            return False
    
    async def _on_fill(self, fill):
        """Record fill to database with PnL tracking."""
        # Calculate PnL if this is a sell
        pnl_realized = 0.0
        if fill.side == 'sell' and fill.metadata:
            pnl_pct = fill.metadata.get('pnl_pct', 0)
            # Calculate dollar PnL based on position value
            position_value = fill.price * fill.amount
            pnl_realized = position_value * (pnl_pct / 100)
        
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency, pnl_realized
        )
    
    def get_stats(self):
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'trades': self.trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.wins / self.trades if self.trades > 0 else 0,
            'total_pnl_pct': self.total_pnl,
            'open_positions': len(self.positions)
        }


async def main():
    print("=" * 70)
    print("MEAN REVERSION SCALPER v2.0")
    print("Strategy: Bollinger Band mean reversion (buy low, sell at mean)")
    print("Position Size: $250 per trade | Target: 0.25% | Stop: 0.4%")
    print("=" * 70)
    
    # Conservative capital allocation
    STARTING_USD = 10000
    
    client = CoinbasePaperClient(
        paper_balances={'USD': STARTING_USD, 'BTC': 0.0, 'ETH': 0.0, 'SOL': 0.0},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./scalper_v2.db')
    await db.connect()
    
    # Sync paper trading balances from database
    print("\n🔄 Syncing paper trading balances from database...")
    conn = sqlite3.connect('./scalper_v2.db')
    cursor = conn.cursor()
    
    # Calculate net position for each asset from fills
    for pair in ['BTC/USD', 'ETH/USD', 'SOL/USD']:
        cursor.execute("SELECT side, amount FROM fills WHERE pair = ?", (pair,))
        fills = cursor.fetchall()
        
        net_position = 0
        for side, amount in fills:
            if side == 'buy':
                net_position += amount
            else:
                net_position -= amount
        
        base = pair.split('/')[0]
        if net_position > 0:
            client.paper_balances[base] = net_position
            print(f"   {base}: {net_position:.6f} (from {len(fills)} fills)")
    
    # Calculate USD spent
    cursor.execute("SELECT side, price, amount FROM fills")
    all_fills = cursor.fetchall()
    usd_spent = 0
    usd_received = 0
    for side, price, amount in all_fills:
        if side == 'buy':
            usd_spent += price * amount
        else:
            usd_received += price * amount
    
    current_usd = STARTING_USD - usd_spent + usd_received
    client.paper_balances['USD'] = max(0, current_usd)
    print(f"   USD: ${current_usd:,.2f} (spent ${usd_spent:,.2f}, received ${usd_received:,.2f})")
    
    conn.close()
    print("✓ Balances synced\n")
    
    # Global state for position limits
    global_state = {'total_open_positions': 0}
    
    # Count current open positions for global state
    for pair in ['BTC/USD', 'ETH/USD', 'SOL/USD']:
        conn = sqlite3.connect('./scalper_v2.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fills WHERE pair = ? AND side = 'buy'", (pair,))
        buys = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM fills WHERE pair = ? AND side = 'sell'", (pair,))
        sells = cursor.fetchone()[0]
        open_lots = buys - sells
        if open_lots > 0:
            global_state['total_open_positions'] += open_lots
            print(f"   {pair}: {open_lots} open lots")
        conn.close()
    
    print(f"🛡️  Total open positions in global state: {global_state['total_open_positions']}")
    
    # Create 3 bots with smaller position sizes
    bots = []
    configs = [
        ('scalp_btc', 'BTC/USD', 300),  # BTC slightly larger
        ('scalp_eth', 'ETH/USD', 250),
        ('scalp_sol', 'SOL/USD', 200)
    ]
    
    print(f"\n💰 Capital: ${STARTING_USD:,} | Risk per trade: 0.4% | Target: 0.25%")
    print(f"🛡️  MAX 3 positions total | 5min cooldown between entries")
    print()
    
    for bot_id, pair, size in configs:
        bot = MeanReversionScalper(
            bot_id=bot_id,
            config=ScalperConfig(pair=pair, order_size_usd=size),
            client=client,
            db=db,
            global_state=global_state
        )
        bots.append((bot_id, bot))
    
    await client.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
    await asyncio.sleep(2)
    
    for bot_id, bot in bots:
        await bot.start()
        print(f"✓ Started {bot_id}")
    
    print("\n" + "=" * 70)
    print("Scalper active. Waiting for Bollinger Band signals...")
    print("=" * 70 + "\n")
    
    try:
        while True:
            await asyncio.sleep(30)  # Update every 30 seconds
            
            usd_bal = client.get_balance('USD').get('available', 0)
            btc_pos = client.get_position('BTC/USD')
            eth_pos = client.get_position('ETH/USD')
            sol_pos = client.get_position('SOL/USD')
            
            total_trades = sum(b.get_stats()['trades'] for _, b in bots)
            total_pnl = sum(b.get_stats()['total_pnl_pct'] for _, b in bots)
            open_pos = sum(b.get_stats()['open_positions'] for _, b in bots)
            
            now = datetime.now().strftime('%H:%M:%S')
            print(f"[{now}] USD: ${usd_bal:,.0f} | Positions: BTC={btc_pos:.4f} ETH={eth_pos:.3f} SOL={sol_pos:.2f} | "
                  f"Open: {open_pos} | Trades: {total_trades} | PnL: {total_pnl:+.2f}%")
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        for _, bot in bots:
            await bot.stop()
        await client.stop()
        await db.close()
        
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)
        total_trades = total_pnl = 0
        for bot_id, bot in bots:
            s = bot.get_stats()
            total_trades += s['trades']
            total_pnl += s['total_pnl_pct']
            print(f"{bot_id}: {s['trades']} trades, {s['win_rate']*100:.0f}% WR, {s['total_pnl_pct']:+.2f}%")
        print("-" * 70)
        print(f"TOTAL: {total_trades} trades, {total_pnl:+.2f}% PnL")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
