#!/usr/bin/env python3
"""
META-TRADER v2.0 - FIXED Balance Tracking
Sells actual available balance, not theoretical position size.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List
import statistics

sys.path.insert(0, str(Path(__file__).parent))

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager


@dataclass
class StrategyPerf:
    name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    active: bool = True
    
    @property
    def win_rate(self):
        return self.wins / self.trades if self.trades > 0 else 0


class SimpleScalper:
    """Fixed scalper - always sells available balance."""
    
    def __init__(self, bot_id: str, pair: str, size: float, client: CoinbasePaperClient, db: DatabaseManager):
        self.bot_id = bot_id
        self.pair = pair
        self.size = size
        self.client = client
        self.db = db
        
        self.is_running = False
        self.prices = []
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.entry_price = None
        self._task = None
        
        self.client.on_fill = self._on_fill
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
    
    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _loop(self):
        while self.is_running:
            try:
                ob = self.client.get_order_book(self.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(1)
                    continue
                
                price = ob.mid_price
                self.prices.append(price)
                if len(self.prices) > 20:
                    self.prices = self.prices[-20:]
                
                if len(self.prices) < 10:
                    await asyncio.sleep(1)
                    continue
                
                # Simple mean reversion
                sma = statistics.mean(self.prices[-10:])
                std = statistics.stdev(self.prices[-10:]) if len(self.prices) >= 10 else 0
                lower = sma - std * 1.5
                upper = sma + std * 1.5
                
                base, quote = self.pair.split('/')
                usd_bal = self.client.get_balance(quote).get('available', 0)
                base_bal = self.client.get_balance(base).get('available', 0)
                
                # Entry: price below lower band, have USD
                if price < lower and usd_bal >= self.size * 1.02 and not self.entry_price:
                    amount = self.size / price
                    order = await self.client.create_limit_order(
                        self.bot_id, self.pair, 'buy', round(price, 2), round(amount, 6), {}
                    )
                    if order:
                        self.entry_price = price
                        print(f"🟢 {self.bot_id}: BUY ${self.size:.0f} @ ${price:.2f}")
                
                # Exit: price above entry + 0.5%, have base
                elif self.entry_price and price > self.entry_price * 1.005 and base_bal > 0.001:
                    # SELL ACTUAL AVAILABLE BALANCE (not theoretical)
                    sell_amount = min(base_bal * 0.99, self.size / self.entry_price * 1.5)  # Cap at 1.5x
                    order = await self.client.create_limit_order(
                        self.bot_id, self.pair, 'sell', round(price, 2), round(sell_amount, 6), {}
                    )
                    if order:
                        pnl = (price - self.entry_price) / self.entry_price * 100
                        self.total_pnl += pnl
                        self.trades += 1
                        if pnl > 0:
                            self.wins += 1
                        else:
                            self.losses += 1
                        
                        emoji = "✅" if pnl > 0 else "❌"
                        print(f"{emoji} {self.bot_id}: SELL {pnl:+.2f}% | Total: {self.total_pnl:+.2f}%")
                        self.entry_price = None
                
                # Stop loss: -1%
                elif self.entry_price and price < self.entry_price * 0.99 and base_bal > 0.001:
                    sell_amount = base_bal * 0.99
                    order = await self.client.create_limit_order(
                        self.bot_id, self.pair, 'sell', round(price, 2), round(sell_amount, 6), {}
                    )
                    if order:
                        pnl = (price - self.entry_price) / self.entry_price * 100
                        self.total_pnl += pnl
                        self.trades += 1
                        self.losses += 1
                        print(f"🛑 {self.bot_id}: STOP {pnl:+.2f}% | Total: {self.total_pnl:+.2f}%")
                        self.entry_price = None
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(2)
    
    async def _on_fill(self, fill):
        await self.db.insert_fill(fill.order_id, fill.fill_id, fill.bot_id,
                                   fill.pair, fill.side, fill.price, fill.amount,
                                   fill.fee, fill.fee_currency)
    
    def get_stats(self):
        return {
            'bot_id': self.bot_id,
            'trades': self.trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.win_rate,
            'total_pnl_pct': self.total_pnl
        }


async def main():
    print("=" * 70)
    print("META-TRADER v2.0 - FIXED BALANCE TRACKING")
    print("Strategy: Mean reversion scalping | Target: +0.5% | Stop: -1%")
    print("=" * 70)
    
    client = CoinbasePaperClient(
        paper_balances={'USD': 10000, 'BTC': 0.0, 'ETH': 0.0, 'SOL': 0.0},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./meta_v2.db')
    await db.connect()
    
    # Create 3 scalpers
    bots = []
    for pair, size in [('BTC/USD', 350), ('ETH/USD', 300), ('SOL/USD', 250)]:
        bot_id = f"scalp_{pair.split('/')[0].lower()}"
        bot = SimpleScalper(bot_id, pair, size, client, db)
        bots.append((bot_id, bot))
    
    await client.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
    await asyncio.sleep(2)
    
    for bot_id, bot in bots:
        await bot.start()
        print(f"✓ Started {bot_id}")
    
    print("\n" + "=" * 70)
    print("Trading. Sells based on ACTUAL available balance.")
    print("=" * 70 + "\n")
    
    try:
        while True:
            await asyncio.sleep(30)
            
            total_trades = sum(b.get_stats()['trades'] for _, b in bots)
            total_pnl = sum(b.get_stats()['total_pnl_pct'] for _, b in bots)
            usd = client.get_balance('USD').get('available', 0)
            
            now = datetime.now().strftime('%H:%M:%S')
            print(f"[{now}] Trades: {total_trades} | PnL: {total_pnl:+.2f}% | USD: ${usd:,.0f}")
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
        for _, bot in bots:
            await bot.stop()
        await client.stop()
        await db.close()
        
        print("\n" + "=" * 70)
        print("FINAL")
        total = 0
        for bot_id, bot in bots:
            s = bot.get_stats()
            total += s['total_pnl_pct']
            print(f"{bot_id}: {s['trades']} trades, {s['win_rate']*100:.0f}% WR, {s['total_pnl_pct']:+.2f}%")
        print(f"TOTAL: {total:+.2f}%")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
