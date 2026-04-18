"""
Grid Trading Bot - Captures volatility through fixed price levels.
Buys at support levels, sells at resistance levels.
Profits from price oscillations within a range.
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

from coinbase_paper_client import CoinbasePaperClient, Order, Fill
from database import DatabaseManager


@dataclass
class GridConfig:
    """Configuration for Grid bot."""
    pair: str
    grid_levels: int  # Number of grid levels
    grid_spacing_pct: float  # % distance between levels
    order_size_usd: float
    max_position: float  # Maximum position in base asset


class GridBot:
    """
    Grid Trading Bot - Places orders at fixed price intervals.
    Captures profits from price bouncing between levels.
    """
    
    def __init__(self, bot_id: str, config: GridConfig,
                 client: CoinbasePaperClient, database: DatabaseManager):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = database
        
        # State
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Grid tracking
        self.grid_orders: Dict[float, Order] = {}  # price level -> order
        self.grid_prices: List[float] = []
        self.center_price: Optional[float] = None
        
        # Stats
        self.total_fills = 0
        self.realized_pnl = 0.0
        
        # Callbacks
        self.client.on_fill = self._on_fill
    
    async def start(self):
        """Start the grid bot."""
        if self.is_running:
            return
        
        self.is_running = True
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """Stop the grid bot."""
        if not self.is_running:
            return
        
        self.is_running = False
        self._shutdown_event.set()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Cancel all grid orders
        for order in list(self.grid_orders.values()):
            if order.status == 'open':
                await self.client.cancel_order(order.id)
    
    async def _main_loop(self):
        """Main grid management loop."""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.best_bid or not ob.best_ask:
                    await asyncio.sleep(1)
                    continue
                
                mid = ob.mid_price
                
                # Initialize or update grid
                if self.center_price is None or abs(mid - self.center_price) / self.center_price > 0.02:
                    # Reset grid if price moved more than 2%
                    await self._setup_grid(mid)
                
                # Check existing orders and fill gaps
                await self._maintain_grid()
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(5)
    
    async def _setup_grid(self, center: float):
        """Set up grid levels around center price."""
        print(f"[{self.bot_id}] Setting up grid around {center:.2f}")
        
        # Clear existing grid orders
        for order in list(self.grid_orders.values()):
            if order.status == 'open':
                await self.client.cancel_order(order.id)
        self.grid_orders.clear()
        
        self.center_price = center
        spacing = center * (self.config.grid_spacing_pct / 100)
        
        # Create grid levels (below and above center)
        self.grid_prices = []
        for i in range(1, self.config.grid_levels // 2 + 1):
            self.grid_prices.append(center - i * spacing)  # Buy levels
            self.grid_prices.append(center + i * spacing)    # Sell levels
        
        self.grid_prices.sort()
        print(f"[{self.bot_id}] Grid levels: {[f'{p:.2f}' for p in self.grid_prices]}")
        
        # Place initial orders
        await self._maintain_grid()
    
    async def _maintain_grid(self):
        """Maintain orders at each grid level."""
        position = self.client.get_position(self.config.pair)
        
        for price in self.grid_prices:
            # Check if we already have an order at this level
            existing = self.grid_orders.get(price)
            if existing and existing.status == 'open':
                continue
            
            # Determine side based on price vs center
            if price < self.center_price:
                side = 'buy'
                # Only buy if position allows
                if position >= self.config.max_position:
                    continue
            else:
                side = 'sell'
                # Only sell if we have inventory
                base = self.config.pair.split('/')[0]
                balance = self.client.get_balance(base)['available']
                if balance <= 0:
                    continue
            
            # Calculate size
            amount = self.config.order_size_usd / price
            
            # Place order
            order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, side,
                round(price, 2), round(amount, 6),
                {'type': f'grid_{side}'}
            )
            
            if order:
                self.grid_orders[price] = order
                await self.db.insert_order(
                    self.bot_id, order.pair, order.id, order.side,
                    order.order_type, order.price, order.amount, order.metadata
                )
                print(f"[{self.bot_id}] Grid {side.upper()}: {amount:.4f} @ ${price:.2f}")
    
    async def _on_fill(self, fill: Fill):
        """Handle grid fill."""
        if fill.bot_id != self.bot_id:
            return
        
        self.total_fills += 1
        
        # Calculate realized PnL
        if fill.side == 'sell':
            # Sold at higher level = profit
            profit = fill.amount * (fill.price - self.center_price)
            self.realized_pnl += profit
            print(f"[{self.bot_id}] ✓ GRID SELL: {fill.amount:.4f} @ ${fill.price:.2f} | PnL: ${profit:.2f}")
        else:
            # Bought at lower level = position entry
            print(f"[{self.bot_id}] ✓ GRID BUY: {fill.amount:.4f} @ ${fill.price:.2f}")
        
        # Log to database
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency
        )
        
        # Remove filled order from grid
        for price, order in list(self.grid_orders.items()):
            if order.id == fill.order_id:
                self.grid_orders.pop(price, None)
                break
    
    def get_stats(self) -> Dict:
        """Get bot statistics."""
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'is_running': self.is_running,
            'center_price': self.center_price,
            'grid_levels': len(self.grid_prices),
            'active_orders': len([o for o in self.grid_orders.values() if o.status == 'open']),
            'total_fills': self.total_fills,
            'realized_pnl': self.realized_pnl
        }
