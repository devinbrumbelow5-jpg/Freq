"""
Bollinger Band Mean Reversion Strategy
Trades price deviations from moving average
Buys when price hits lower band, sells at mean
Sells when price hits upper band, buys at mean
"""

import asyncio
from collections import deque
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import statistics

from coinbase_paper_client import CoinbasePaperClient, Order, Fill
from database import DatabaseManager


@dataclass
class BBConfig:
    pair: str
    period: int = 20  # Lookback period
    std_dev: float = 2.0  # Standard deviations for bands
    order_size_usd: float = 200
    stop_loss_pct: float = 1.0  # Stop if price moves 1% against position
    take_profit_pct: float = 0.5  # Target 0.5% profit


class BollingerBot:
    """
    Bollinger Band mean reversion strategy.
    Only trades when price hits statistical extremes.
    """
    
    def __init__(self, bot_id: str, config: BBConfig,
                 client: CoinbasePaperClient, database: DatabaseManager):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = database
        
        # State
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        
        # Price history
        self.prices: deque = deque(maxlen=config.period + 10)
        self.position: float = 0.0
        self.entry_price: Optional[float] = None
        
        # Stats
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        
        # Callbacks
        self.client.on_fill = self._on_fill
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._main_loop())
    
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
    
    def _calculate_bands(self) -> Optional[Dict]:
        """Calculate Bollinger Bands using statistics module."""
        if len(self.prices) < self.config.period:
            return None
        
        prices = list(self.prices)[-self.config.period:]
        sma = statistics.mean(prices)
        std = statistics.stdev(prices)
        
        return {
            'upper': sma + (std * self.config.std_dev),
            'middle': sma,
            'lower': sma - (std * self.config.std_dev)
        }
    
    async def _main_loop(self):
        """Main strategy loop."""
        while self.is_running:
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(1)
                    continue
                
                price = ob.mid_price
                self.prices.append(price)
                
                bands = self._calculate_bands()
                if not bands:
                    await asyncio.sleep(1)
                    continue
                
                # Update position
                self.position = self.client.get_position(self.config.pair)
                
                # Check for exit conditions first
                if self.position != 0 and self.entry_price:
                    pnl_pct = ((price - self.entry_price) / self.entry_price) * 100
                    if self.position > 0:  # Long position
                        pnl_pct = -pnl_pct  # Invert for long
                    
                    # Stop loss
                    if pnl_pct < -self.config.stop_loss_pct:
                        await self._close_position(price, "stop_loss")
                        continue
                    
                    # Take profit
                    if pnl_pct > self.config.take_profit_pct:
                        await self._close_position(price, "take_profit")
                        continue
                
                # Entry logic (only if flat)
                if self.position == 0:
                    # Price below lower band = buy signal
                    if price < bands['lower']:
                        amount = self.config.order_size_usd / price
                        order = await self.client.create_limit_order(
                            self.bot_id, self.config.pair, 'buy',
                            round(price, 2), round(amount, 6),
                            {'signal': 'bb_lower', 'band': bands['lower']}
                        )
                        if order:
                            self.entry_price = price
                            print(f"[{self.bot_id}] 📉 BUY @ ${price:.2f} (lower band: ${bands['lower']:.2f})")
                    
                    # Price above upper band = sell signal
                    elif price > bands['upper']:
                        base = self.config.pair.split('/')[0]
                        bal = self.client.get_balance(base)['available']
                        amount = min(self.config.order_size_usd / price, bal * 0.5)
                        if amount > 0.001:
                            order = await self.client.create_limit_order(
                                self.bot_id, self.config.pair, 'sell',
                                round(price, 2), round(amount, 6),
                                {'signal': 'bb_upper', 'band': bands['upper']}
                            )
                            if order:
                                self.entry_price = price
                                print(f"[{self.bot_id}] 📈 SELL @ ${price:.2f} (upper band: ${bands['upper']:.2f})")
                
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(5)
    
    async def _close_position(self, price: float, reason: str):
        """Close current position."""
        if self.position > 0:
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'sell',
                round(price, 2), abs(self.position),
                {'close_reason': reason}
            )
        elif self.position < 0:
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'buy',
                round(price, 2), abs(self.position),
                {'close_reason': reason}
            )
        
        if order:
            pnl = (price - self.entry_price) / self.entry_price * 100
            if self.position < 0:
                pnl = -pnl
            
            self.total_pnl += pnl
            if pnl > 0:
                self.wins += 1
            else:
                self.losses += 1
            
            print(f"[{self.bot_id}] ✓ CLOSED ({reason}): PnL {pnl:.2f}% | Total: ${self.total_pnl:.2f}")
            self.position = 0
            self.entry_price = None
    
    async def _on_fill(self, fill: Fill):
        """Handle fill."""
        if fill.bot_id != self.bot_id:
            return
        
        self.trades += 1
        
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency
        )
    
    def get_stats(self) -> Dict:
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'trades': self.trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.wins / (self.wins + self.losses) if (self.wins + self.losses) > 0 else 0,
            'total_pnl': self.total_pnl
        }
