"""
PMM Bot - Individual market maker bot implementation.
Dynamic spread calculation, inventory skew, order management.
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import math

from kraken_paper_client import KrakenPaperClient, Order, Fill
from database import DatabaseManager


@dataclass
class PMMConfig:
    """Configuration for a PMM bot."""
    pair: str
    base_spread_bps: float
    order_amount_usd: float
    max_position_pct: float
    
    # Derived
    @property
    def base_spread(self) -> float:
        return self.base_spread_bps / 10000  # Convert bps to decimal


class PMMBot:
    """
    Perpetual Market Maker Bot.
    Maintains buy and sell orders around mid price with dynamic spread.
    """
    
    def __init__(self, bot_id: str, config: PMMConfig, 
                 client: KrakenPaperClient, database: DatabaseManager,
                 refresh_interval: float = 10.0, 
                 price_move_threshold: float = 0.0015):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = database
        self.refresh_interval = refresh_interval
        self.price_move_threshold = price_move_threshold
        
        # State
        self.is_running = False
        self.current_bid: Optional[float] = None
        self.current_ask: Optional[float] = None
        self.last_mid_price: Optional[float] = None
        self.position_size: float = 0.0  # In base asset
        self.position_value: float = 0.0  # In USD
        self.inventory_skew: float = 0.0  # -1 to 1
        self.orders_open: int = 0
        
        # Order IDs
        self.active_bid_id: Optional[str] = None
        self.active_ask_id: Optional[str] = None
        
        # Stats
        self.total_fills: int = 0
        self.last_fill_time: Optional[float] = None
        
        # Async
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the bot."""
        if self.is_running:
            return
        
        self.is_running = True
        self._shutdown_event.clear()
        
        # Set callbacks
        self.client.on_fill = self._on_fill
        self.client.on_order_update = self._on_order_update
        
        # Update DB status
        await self.db.update_bot_status(
            self.bot_id, self.config.pair, True
        )
        
        # Start main loop
        self._task = asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """Stop the bot gracefully."""
        if not self.is_running:
            return
        
        self.is_running = False
        self._shutdown_event.set()
        
        # Cancel all orders
        await self.client.cancel_all_orders(self.bot_id)
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Update DB status
        await self.db.update_bot_status(
            self.bot_id, self.config.pair, False
        )
    
    async def _main_loop(self):
        """Main bot loop - place and refresh orders."""
        last_refresh = 0
        
        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Get current order book
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.mid_price:
                    await asyncio.sleep(0.5)
                    continue
                
                mid_price = ob.mid_price
                now = datetime.utcnow().timestamp()
                
                # Check if refresh needed
                need_refresh = False
                
                # Time-based refresh
                if now - last_refresh > self.refresh_interval:
                    need_refresh = True
                
                # Price move refresh
                if self.last_mid_price:
                    price_change = abs(mid_price - self.last_mid_price) / self.last_mid_price
                    if price_change > self.price_move_threshold:
                        need_refresh = True
                
                if need_refresh:
                    await self._refresh_orders(mid_price, ob)
                    last_refresh = now
                    self.last_mid_price = mid_price
                
                # Update stats
                await self._update_position_stats(mid_price)
                
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(1)
    
    async def _refresh_orders(self, mid_price: float, ob):
        """Cancel old orders and place new ones."""
        # Calculate dynamic spread
        spread = self._calculate_spread(ob)
        
        # Calculate inventory skew
        skew = self._calculate_inventory_skew()
        
        # Apply skew to prices
        bid_skew = -skew * spread * 0.5  # Shift bid down when long
        ask_skew = skew * spread * 0.5   # Shift ask up when short
        
        new_bid = mid_price * (1 - spread / 2 + bid_skew)
        new_ask = mid_price * (1 + spread / 2 + ask_skew)
        
        # Get order amounts
        bid_amount = self._calculate_order_amount('buy', mid_price)
        ask_amount = self._calculate_order_amount('sell', mid_price)
        
        # Cancel existing orders
        cancel_tasks = []
        if self.active_bid_id:
            cancel_tasks.append(self.client.cancel_order(self.active_bid_id))
        if self.active_ask_id:
            cancel_tasks.append(self.client.cancel_order(self.active_ask_id))
        if cancel_tasks:
            await asyncio.gather(*cancel_tasks, return_exceptions=True)
            self.active_bid_id = None
            self.active_ask_id = None
        
        # Place new orders (with small delay to ensure cancels processed)
        await asyncio.sleep(0.1)
        
        if bid_amount > 0:
            bid_order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'buy', new_bid, bid_amount,
                {'type': 'pmm_bid', 'mid_price': mid_price}
            )
            if bid_order:
                self.active_bid_id = bid_order.id
                try:
                    await self.db.insert_order(
                        self.bot_id, self.config.pair, bid_order.id,
                        'buy', 'limit', new_bid, bid_amount,
                        {'mid_price': mid_price}
                    )
                except Exception as e:
                    pass  # DB errors non-critical
        
        if ask_amount > 0:
            ask_order = await self.client.create_limit_order(
                self.bot_id, self.config.pair, 'sell', new_ask, ask_amount,
                {'type': 'pmm_ask', 'mid_price': mid_price}
            )
            if ask_order:
                self.active_ask_id = ask_order.id
                try:
                    await self.db.insert_order(
                        self.bot_id, self.config.pair, ask_order.id,
                        'sell', 'limit', new_ask, ask_amount,
                        {'mid_price': mid_price}
                    )
                except Exception as e:
                    pass  # DB errors non-critical
        
        # Update state
        self.current_bid = new_bid
        self.current_ask = new_ask
        
        # Count open orders
        orders = self.client.get_orders(self.bot_id, 'open')
        self.orders_open = len(orders)
    
    def _calculate_spread(self, ob) -> float:
        """Calculate dynamic spread based on order book."""
        base_spread = self.config.base_spread
        
        # Widen spread if market spread is wide
        market_spread = ob.spread_bps / 10000  # Convert to decimal
        spread = max(base_spread, market_spread * 1.2)
        
        # Widen spread if volatility is high (based on order book depth)
        if ob.bids and ob.asks:
            bid_depth = sum(b[1] for b in ob.bids[:5])
            ask_depth = sum(a[1] for a in ob.asks[:5])
            imbalance = abs(bid_depth - ask_depth) / (bid_depth + ask_depth + 1e-10)
            spread *= (1 + imbalance * 0.5)  # Up to 50% wider
        
        return spread
    
    def _calculate_inventory_skew(self) -> float:
        """Calculate inventory skew (-1 to 1)."""
        # Get position
        position = self.client.get_position(self.config.pair)
        
        if position == 0:
            return 0.0
        
        # Calculate as percentage of max allowed
        max_position = self._get_max_position_size()
        skew = position / max_position if max_position > 0 else 0
        
        # Clamp to -1 to 1
        return max(-1, min(1, skew))
    
    def _calculate_order_amount(self, side: str, mid_price: float) -> float:
        """Calculate order amount in base asset."""
        usd_amount = self.config.order_amount_usd
        
        # Reduce size if approaching position limit
        position = self.client.get_position(self.config.pair)
        max_position = self._get_max_position_size()
        
        if side == 'buy' and position >= 0:
            remaining = max_position - position
            base_amount = min(usd_amount / mid_price, remaining)
        elif side == 'buy' and position < 0:
            # Can buy more if short
            base_amount = usd_amount / mid_price
        elif side == 'sell' and position <= 0:
            remaining = max_position + position  # position is negative
            base_amount = min(usd_amount / mid_price, remaining)
        else:  # sell and long
            base_amount = usd_amount / mid_price
        
        # Round to 6 decimals
        return round(max(0, base_amount), 6)
    
    def _get_max_position_size(self) -> float:
        """Get max position size in base asset."""
        # Assume $10k starting capital per bot
        capital = 10000
        max_usd = capital * self.config.max_position_pct
        # Rough estimate using current price or default
        price = self.last_mid_price or 100
        return max_usd / price
    
    async def _update_position_stats(self, mid_price: float):
        """Update position and stats."""
        self.position_size = self.client.get_position(self.config.pair)
        self.position_value = self.position_size * mid_price
        self.inventory_skew = self._calculate_inventory_skew()
        
        # Update DB (non-critical)
        spread_bps = 0
        if self.current_bid and self.current_ask:
            spread = (self.current_ask - self.current_bid) / mid_price
            spread_bps = spread * 10000
        
        try:
            await self.db.update_bot_status(
                self.bot_id, self.config.pair, self.is_running,
                self.current_bid, self.current_ask, mid_price,
                spread_bps, self.position_size, self.position_value,
                self.inventory_skew, self.orders_open
            )
        except Exception:
            pass
    
    async def _on_fill(self, fill: Fill):
        """Handle fill callback."""
        if fill.bot_id != self.bot_id:
            return
        
        self.total_fills += 1
        self.last_fill_time = fill.timestamp
        
        # Record in DB
        await self.db.insert_fill(
            fill.order_id, fill.fill_id, fill.bot_id,
            fill.pair, fill.side, fill.price, fill.amount,
            fill.fee, fill.fee_currency
        )
        
        # Update P&L
        today = datetime.utcnow().strftime("%Y-%m-%d")
        pnl = self.client.calculate_pnl(self.bot_id, self.config.pair)
        await self.db.update_pnl(
            self.bot_id, self.config.pair, today,
            realized_pnl=pnl['realized_pnl'],
            fees_paid=pnl['fees']
        )
        
        print(f"[{self.bot_id}] Fill: {fill.side} {fill.amount:.6f} @ {fill.price:.4f}")
    
    async def _on_order_update(self, order: Order):
        """Handle order update callback."""
        if order.bot_id != self.bot_id:
            return
        
        await self.db.update_order_status(order.id, order.status, order.filled)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current bot stats."""
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'is_running': self.is_running,
            'bid': self.current_bid,
            'ask': self.current_ask,
            'position_size': self.position_size,
            'position_value': self.position_value,
            'inventory_skew': self.inventory_skew,
            'orders_open': self.orders_open,
            'total_fills': self.total_fills,
            'last_fill_time': self.last_fill_time
        }
