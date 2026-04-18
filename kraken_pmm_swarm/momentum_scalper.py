"""
Momentum Breakout Scalper - Trend following with tight stops.
For trending markets where market making fails.
"""

import asyncio
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager


@dataclass
class MomentumConfig:
    pair: str
    order_amount_usd: float
    breakout_threshold_pct: float  # Entry when price moves X%
    stop_loss_pct: float
    take_profit_pct: float
    max_position_pct: float


class MomentumScalper:
    """
    Trend-following scalper. Enters on breakout, exits on stop/target.
    Better for trending markets than market making.
    """
    
    def __init__(self, bot_id: str, config: MomentumConfig,
                 client: CoinbasePaperClient, database: DatabaseManager):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = database
        
        self.is_running = False
        self.position: float = 0.0
        self.entry_price: Optional[float] = None
        self._task: Optional[asyncio.Task] = None
        
        self.client.register_fill_callback(self.bot_id, self._on_fill)
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._main_loop())
        print(f"[{self.bot_id}] Momentum scalper started on {self.config.pair}")
    
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
    
    async def _main_loop(self):
        """Main trading loop - momentum breakout strategy."""
        prices = []
        
        while self.is_running:
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(0.5)
                    continue
                
                mid = ob.mid_price
                prices.append(mid)
                if len(prices) > 60:  # Keep last 60 ticks (~60 seconds)
                    prices.pop(0)
                
                if len(prices) < 10:
                    await asyncio.sleep(1)
                    continue
                
                # Calculate momentum
                avg_price = sum(prices) / len(prices)
                momentum = (mid - avg_price) / avg_price if avg_price > 0 else 0
                momentum_pct = momentum * 100
                
                # Update position tracking
                self.position = self.client.get_position(self.config.pair)
                
                # Check for entry/exit signals
                if self.position == 0:  # No position - look for entry
                    threshold = self.config.breakout_threshold_pct / 100
                    
                    if momentum_pct > threshold:  # Bullish breakout
                        # Go long
                        usd_avail = self.client.get_balance('USD')['available']
                        size_usd = min(self.config.order_amount_usd, usd_avail * 0.3)
                        if size_usd > 10:
                            amount = round(size_usd / mid, 6)
                            order = await self.client.create_limit_order(
                                self.bot_id, self.config.pair, 'buy',
                                mid * 1.0001, amount, {'type': 'momentum_entry'}
                            )
                            if order:
                                self.entry_price = mid
                                print(f"[{self.bot_id}] 📈 LONG ENTRY @ {mid:,.2f} (momentum: +{momentum_pct:.3f}%)")
                    
                    elif momentum_pct < -threshold:  # Bearish breakout
                        # Go short (if we have asset)
                        base = self.config.pair.split('/')[0]
                        base_avail = self.client.get_balance(base)['available']
                        size = min(self.config.order_amount_usd / mid, base_avail * 0.5)
                        if size > 0.0001:
                            order = await self.client.create_limit_order(
                                self.bot_id, self.config.pair, 'sell',
                                mid * 0.9999, size, {'type': 'momentum_entry'}
                            )
                            if order:
                                self.entry_price = mid
                                print(f"[{self.bot_id}] 📉 SHORT ENTRY @ {mid:,.2f} (momentum: {momentum_pct:.3f}%)")
                
                else:  # Have position - check exit conditions
                    if self.entry_price:
                        pnl_pct = (mid - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
                        
                        # Exit conditions
                        if self.position > 0:  # Long
                            if pnl_pct >= self.config.take_profit_pct / 100:
                                print(f"[{self.bot_id}] ✅ TAKE PROFIT: {pnl_pct*100:.2f}%")
                                await self._exit_position(mid)
                            elif pnl_pct <= -self.config.stop_loss_pct / 100:
                                print(f"[{self.bot_id}] 🛑 STOP LOSS: {pnl_pct*100:.2f}%")
                                await self._exit_position(mid)
                        
                        else:  # Short
                            if -pnl_pct >= self.config.take_profit_pct / 100:
                                print(f"[{self.bot_id}] ✅ TAKE PROFIT (short): {-pnl_pct*100:.2f}%")
                                await self._exit_position(mid)
                            elif -pnl_pct <= -self.config.stop_loss_pct / 100:
                                print(f"[{self.bot_id}] 🛑 STOP LOSS (short): {-pnl_pct*100:.2f}%")
                                await self._exit_position(mid)
                
                await self.db.update_bot_status(
                    self.bot_id, self.config.pair, self.is_running,
                    ob.best_bid, ob.best_ask, mid, ob.spread_bps,
                    self.position, self.position * mid, 0.0, 0
                )
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(2)
    
    async def _exit_position(self, price: float):
        """Exit current position."""
        if self.position > 0:
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'sell',
                price * 0.9999, self.position, {'type': 'momentum_exit'}
            )
        elif self.position < 0:
            base = self.config.pair.split('/')[0]
            usd_needed = abs(self.position) * price
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'buy',
                price * 1.0001, abs(self.position), {'type': 'momentum_exit'}
            )
    
    async def _on_fill(self, fill):
        """Handle fill."""
        if fill.bot_id != self.bot_id:
            return
        
        if fill.side == 'buy':
            self.position += fill.amount
        else:
            self.position -= fill.amount
        
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency
        )
        
        print(f"[{self.bot_id}] Fill: {fill.side} {fill.amount:.6f} @ ${fill.price:,.2f}")
        
        # Reset entry price on exit
        if abs(self.position) < 0.0001:
            self.entry_price = None
