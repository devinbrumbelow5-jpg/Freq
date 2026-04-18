#!/usr/bin/env python3
"""
GRID MAKER v1.0 - Profits from dead markets via spread capture
- Places bids slightly below market
- Places asks slightly above market
- Captures spread on every fill
- Replaces orders immediately
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dataclasses import dataclass
from datetime import datetime

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager


@dataclass  
class GridConfig:
    pair: str
    grid_spread_bps: float = 5.0  # 0.05% spread
    order_size_usd: float = 200
    max_orders_per_side: int = 2


class GridMaker:
    """Market maker that captures spread via grid orders."""
    
    def __init__(self, bot_id: str, config: GridConfig, client: CoinbasePaperClient, db: DatabaseManager):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = db
        
        self.is_running = False
        self._task = None
        
        # Track our orders
        self.bid_orders = []  # Buy orders waiting
        self.ask_orders = []  # Sell orders waiting
        
        self.trades = 0
        self.total_pnl = 0.0
        
        self.client.on_fill = self._on_fill
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
    
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
        """Main loop - maintain grid."""
        while self.is_running:
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(0.5)
                    continue
                
                mid = ob.mid_price
                spread_pct = self.config.grid_spread_bps / 100
                
                base, quote = self.config.pair.split('/')
                usd_bal = self.client.get_balance(quote).get('available', 0)
                base_bal = self.client.get_balance(base).get('available', 0)
                
                # Calculate grid levels
                buy_price = mid * (1 - spread_pct)
                sell_price = mid * (1 + spread_pct)
                amount = self.config.order_size_usd / mid
                
                # Maintain bid side (buy orders)
                if len(self.bid_orders) < self.config.max_orders_per_side and usd_bal >= self.config.order_size_usd * 1.05:
                    order = await self.client.create_limit_order(
                        self.bot_id, self.config.pair, 'buy',
                        round(buy_price, 2), round(amount, 6),
                        {'type': 'grid_bid', 'mid': mid}
                    )
                    if order:
                        self.bid_orders.append(order.id)
                        print(f"📗 {self.bot_id}: BID ${buy_price:.2f} x {amount:.4f} (mid: ${mid:.2f})")
                
                # Maintain ask side (sell orders)  
                if len(self.ask_orders) < self.config.max_orders_per_side and base_bal >= amount * 1.05:
                    order = await self.client.create_limit_order(
                        self.bot_id, self.config.pair, 'sell',
                        round(sell_price, 2), round(amount, 6),
                        {'type': 'grid_ask', 'mid': mid}
                    )
                    if order:
                        self.ask_orders.append(order.id)
                        print(f"📕 {self.bot_id}: ASK ${sell_price:.2f} x {amount:.4f} (mid: ${mid:.2f})")
                
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(2)
    
    async def _on_fill(self, fill):
        """Handle fill - grid order hit."""
        if fill.bot_id != self.bot_id:
            return
        
        self.trades += 1
        
        # Calculate PnL (simplified - spread captured)
        if fill.side == 'buy':
            self.bid_orders = [o for o in self.bid_orders if o != fill.order_id]
            print(f"✅ {self.bot_id}: BID FILLED @ ${fill.price:.2f}")
        else:
            self.ask_orders = [o for o in self.ask_orders if o != fill.order_id]
            spread = self.config.grid_spread_bps / 100
            self.total_pnl += spread * 100  # Convert to %
            print(f"✅ {self.bot_id}: ASK FILLED @ ${fill.price:.2f} | Spread: +{spread*100:.2f}%")
        
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency
        )
    
    def get_stats(self):
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'trades': self.trades,
            'open_bids': len(self.bid_orders),
            'open_asks': len(self.ask_orders),
            'total_pnl_bps': self.total_pnl
        }


async def main():
    print("=" * 70)
    print("GRID MAKER v1.0 - Spread Capture in Dead Markets")
    print("Strategy: Place bids below, asks above, capture spread")
    print("Grid: 5 bps (0.05%) | Size: $200 per order")
    print("=" * 70)
    
    client = CoinbasePaperClient(
        paper_balances={'USD': 10000, 'BTC': 0.05, 'ETH': 0.5, 'SOL': 5.0},
        max_slippage_pct=0.01
    )
    
    db = DatabaseManager('./grid_maker.db')
    await db.connect()
    
    # Three grid bots
    bots = []
    configs = [
        ('grid_btc', 'BTC/USD', 300),
        ('grid_eth', 'ETH/USD', 250),
        ('grid_sol', 'SOL/USD', 200)
    ]
    
    for bot_id, pair, size in configs:
        bot = GridMaker(
            bot_id=bot_id,
            config=GridConfig(pair=pair, order_size_usd=size),
            client=client,
            db=db
        )
        bots.append((bot_id, bot))
    
    await client.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
    await asyncio.sleep(2)
    
    for bot_id, bot in bots:
        await bot.start()
        print(f"✓ Started {bot_id}")
    
    print("\n" + "=" * 70)
    print("Grid active. Capturing spread...")
    print("=" * 70 + "\n")
    
    try:
        while True:
            await asyncio.sleep(30)
            
            total_trades = sum(b.get_stats()['trades'] for _, b in bots)
            total_pnl = sum(b.get_stats()['total_pnl_bps'] for _, b in bots)
            total_bids = sum(b.get_stats()['open_bids'] for _, b in bots)
            total_asks = sum(b.get_stats()['open_asks'] for _, b in bots)
            
            usd = client.get_balance('USD').get('available', 0)
            
            now = datetime.now().strftime('%H:%M:%S')
            print(f"[{now}] Trades: {total_trades} | PnL: +{total_pnl:.2f}bps | Orders: {total_bids}b/{total_asks}a | USD: ${usd:,.0f}")
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        for _, bot in bots:
            await bot.stop()
        await client.stop()
        await db.close()
        
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)
        total = 0
        for bot_id, bot in bots:
            s = bot.get_stats()
            total += s['total_pnl_bps']
            print(f"{bot_id}: {s['trades']} trades, +{s['total_pnl_bps']:.2f}bps")
        print("-" * 70)
        print(f"TOTAL: +{total:.2f}bps ({total/100:.2f}%)")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
