#!/usr/bin/env python3
"""
ADAPTIVE META-TRADER v1.0
Watches multiple strategies, allocates to winners, kills losers automatically.
"""

import asyncio
import sys
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager
from ema_bot import EMACrossoverBot, EMAConfig
from bollinger_bot import BollingerBot, BBConfig


@dataclass
class StrategyPerformance:
    name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    last_trade_time: Optional[datetime] = None
    active: bool = True
    capital_allocation: float = 0.33  # Start equal
    
    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades > 0 else 0
    
    @property
    def avg_trade(self) -> float:
        return self.total_pnl / self.trades if self.trades > 0 else 0
    
    def score(self) -> float:
        """Strategy score for capital allocation."""
        if self.trades < 3:
            return 0.33  # Neutral until proven
        return self.win_rate * max(0, self.avg_trade * 100)  # Win rate * avg return


class AdaptiveMetaTrader:
    """
    Meta-strategy that manages multiple sub-strategies.
    Allocates capital to best performers, kills losers.
    """
    
    def __init__(self, client: CoinbasePaperClient, db: DatabaseManager):
        self.client = client
        self.db = db
        self.is_running = False
        
        # Strategy instances
        self.strategies: Dict[str, any] = {}
        self.performance: Dict[str, StrategyPerformance] = {}
        
        # Parameters
        self.rebalance_interval = 300  # 5 min
        self.kill_threshold = -2.0  # Kill if -2% PnL
        self.min_trades_for_eval = 5
        
        self._task = None
    
    async def start(self, pairs: List[str]):
        """Initialize all strategies for all pairs."""
        self.is_running = True
        
        # Start WebSocket
        await self.client.start(pairs)
        await asyncio.sleep(3)
        
        # Initialize strategies per pair
        for pair in pairs:
            base = pair.split('/')[0]
            
            # EMA Strategy (trend following)
            ema_id = f"ema_{base.lower()}"
            ema_bot = EMACrossoverBot(
                ema_id, EMAConfig(pair=pair, order_size_usd=300),
                self.client, self.db
            )
            self.strategies[ema_id] = ema_bot
            self.performance[ema_id] = StrategyPerformance(name=ema_id)
            await ema_bot.start()
            
            # Bollinger Strategy (mean reversion)
            bb_id = f"bb_{base.lower()}"
            bb_bot = BollingerBot(
                bb_id, BBConfig(pair=pair, order_size_usd=300),
                self.client, self.db
            )
            self.strategies[bb_id] = bb_bot
            self.performance[bb_id] = StrategyPerformance(name=bb_id)
            await bb_bot.start()
            
            print(f"✓ Initialized strategies for {pair}")
        
        # Start meta-manager
        self._task = asyncio.create_task(self._meta_loop())
    
    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        for bot in self.strategies.values():
            await bot.stop()
        await self.client.stop()
    
    async def _meta_loop(self):
        """Main meta-management loop."""
        while self.is_running:
            try:
                await self._evaluate_strategies()
                await self._rebalance_capital()
                await self._report_status()
                await asyncio.sleep(self.rebalance_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[META] Error: {e}")
                await asyncio.sleep(10)
    
    async def _evaluate_strategies(self):
        """Evaluate each strategy's performance."""
        for bot_id, bot in self.strategies.items():
            perf = self.performance[bot_id]
            stats = bot.get_stats()
            
            # Update performance
            perf.trades = stats.get('trades', 0)
            perf.wins = stats.get('wins', 0)
            perf.losses = stats.get('losses', 0)
            perf.total_pnl = stats.get('total_pnl_pct', 0)
            
            # Check kill conditions
            if perf.trades >= self.min_trades_for_eval:
                if perf.total_pnl < self.kill_threshold:
                    print(f"🛑 [META] Killing {bot_id}: PnL {perf.total_pnl:.2f}% below threshold")
                    perf.active = False
                    await bot.stop()
                elif perf.win_rate < 0.3 and perf.trades > 10:
                    print(f"🛑 [META] Killing {bot_id}: Win rate {perf.win_rate*100:.0f}% too low")
                    perf.active = False
                    await bot.stop()
    
    async def _rebalance_capital(self):
        """Reallocate capital based on performance."""
        active_perfs = [p for p in self.performance.values() if p.active]
        if len(active_perfs) < 2:
            return
        
        # Calculate scores
        scores = {p.name: p.score() for p in active_perfs}
        total_score = sum(scores.values()) or 1
        
        # Reallocate proportionally
        for perf in active_perfs:
            new_allocation = scores[perf.name] / total_score
            perf.capital_allocation = max(0.1, min(0.7, new_allocation))  # Clamp 10-70%
    
    async def _report_status(self):
        """Print status report."""
        print(f"\n{'='*70}")
        print(f"META-TRADER STATUS | {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")
        
        total_trades = sum(p.trades for p in self.performance.values())
        total_pnl = sum(p.total_pnl for p in self.performance.values())
        active_count = sum(1 for p in self.performance.values() if p.active)
        
        print(f"Active Strategies: {active_count}/{len(self.strategies)}")
        print(f"Total Trades: {total_trades} | Combined PnL: {total_pnl:+.2f}%")
        print(f"{'-'*70}")
        
        for bot_id, perf in sorted(self.performance.items(), key=lambda x: x[1].score(), reverse=True):
            status = "🟢" if perf.active else "🔴"
            print(f"{status} {bot_id:12s} | Trades: {perf.trades:3d} | "
                  f"WR: {perf.win_rate*100:5.1f}% | PnL: {perf.total_pnl:+6.2f}% | "
                  f"Alloc: {perf.capital_allocation*100:4.0f}% | Score: {perf.score():.2f}")
        
        print(f"{'='*70}\n")


async def main():
    print("=" * 70)
    print("ADAPTIVE META-TRADER v1.0")
    print("Manages multiple strategies, kills losers, scales winners")
    print("=" * 70)
    
    client = CoinbasePaperClient(
        paper_balances={'USD': 10000, 'BTC': 0.05, 'ETH': 0.3, 'SOL': 3.0},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./meta_trader.db')
    await db.connect()
    
    trader = AdaptiveMetaTrader(client, db)
    
    try:
        await trader.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
        
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\nShutting down meta-trader...")
        await trader.stop()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
