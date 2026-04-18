"""
Passive Market Maker - Places maker orders on both sides of the spread.
Earns spread instead of paying it. Waits to be filled by takers.
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import random

from coinbase_paper_client import CoinbasePaperClient, Order, Fill
from database import DatabaseManager


@dataclass
class AMMConfig:
    """Configuration for Aggressive MM bot."""
    pair: str
    min_edge_bps: float  # Minimum edge required to cross (profit margin)
    order_amount_usd: float
    max_position_pct: float
    
    @property
    def min_edge(self) -> float:
        return self.min_edge_bps / 10000


class PassiveMarketMaker:
    """
    Passive Market Maker - Posts bid/ask quotes, earns spread.
    Places orders at bid + edge and ask - edge (maker orders).
    """
    
    # Track global fills across all instances
    _global_fills: Dict[str, int] = {}
    
    def __init__(self, bot_id: str, config: AMMConfig, 
                 client: CoinbasePaperClient, database: DatabaseManager):
        self.bot_id = bot_id
        self.config = config
        self.client = client
        self.db = database
        
        # State
        self.is_running = False
        self.last_trade_time: Optional[float] = None
        self.total_fills: int = 0
        self.position: float = 0.0
        
        # Async
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Callbacks - Register with client using new callback system
        self.client.register_fill_callback(self.bot_id, self._on_fill)
    
    async def start(self):
        """Start the bot."""
        if self.is_running:
            return
        
        self.is_running = True
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """Stop the bot."""
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
    
    async def _main_loop(self):
        """Main trading loop - PASSIVE MARKET MAKING."""
        # Track active orders
        self._active_orders: Dict[str, Order] = {}
        
        while self.is_running and not self._shutdown_event.is_set():
            try:
                ob = self.client.get_order_book(self.config.pair)
                if not ob or not ob.best_bid or not ob.best_ask:
                    await asyncio.sleep(0.5)
                    continue
                
                mid = ob.mid_price
                spread_bps = ob.spread_bps
                
                # Update position tracking
                self.position = self.client.get_position(self.config.pair)
                
                # AGGRESSIVE: Tighter edge = 1-2.5 bps for more fills
                cfg_spread = getattr(self.config, 'base_spread_bps', 2)
                maker_edge_bps = cfg_spread * 0.5  # Half on each side
                bid_price = mid * (1 - maker_edge_bps / 10000)
                ask_price = mid * (1 + maker_edge_bps / 10000)
                
                # Very tight to spread
                bid_price = min(bid_price, ob.best_bid * 1.00005)
                ask_price = max(ask_price, ob.best_ask * 0.99995)
                
                # Round to proper precision
                price_decimals = 2 if 'USD' in self.config.pair else 4
                bid_price = round(bid_price, price_decimals)
                ask_price = round(ask_price, price_decimals)
                
                # Get position and calculate sizing from config
                max_pos_usd = 2000 * self.config.max_position_pct  # ~$600 per pair
                max_pos_asset = max_pos_usd / mid
                
                # Check if we need to adjust orders
                current_orders = [o for o in self._active_orders.values() 
                                 if o.status == 'open' and o.pair == self.config.pair]
                
                has_bid = any(o.side == 'buy' for o in current_orders)
                has_ask = any(o.side == 'sell' for o in current_orders)
                
                # Inventory skew: reduce size when building long position
                position_ratio = self.position / max_pos_asset if max_pos_asset > 0 else 0
                skew_factor = max(0.3, 1.0 - position_ratio)  # 30% minimum, scales down as position grows
                
                # Place bid if position allows and no existing bid
                if not has_bid and self.position < max_pos_asset * 0.9:
                    usd_avail = self.client.get_balance('USD')['available']
                    bid_size_usd = min(self.config.order_amount_usd * skew_factor, usd_avail * 0.2)
                    if bid_size_usd > 10:  # Minimum $10 order
                        amount = round(bid_size_usd / bid_price, 6)
                        order = await self.client.create_limit_order(
                            self.bot_id, self.config.pair, 'buy',
                            bid_price, amount, {'type': 'maker_bid'}
                        )
                        if order:
                            self._active_orders[order.id] = order
                            await self.db.insert_order(
                                self.bot_id, order.pair, order.id, order.side,
                                order.order_type, order.price, order.amount, order.metadata
                            )
                            print(f"[{self.bot_id}] MAKER BID: {amount:.6f} @ ${bid_price:,.2f}")
                
                # Place ask if position allows and no existing ask
                if not has_ask and self.position > -max_pos_asset * 0.9:
                    base = self.config.pair.split('/')[0]
                    base_avail = self.client.get_balance(base)['available']
                    ask_size = min(self.config.order_amount_usd / ask_price * skew_factor, base_avail * 0.5)
                    if ask_size > 0.0001:
                        order = await self.client.create_limit_order(
                            self.bot_id, self.config.pair, 'sell',
                            ask_price, ask_size, {'type': 'maker_ask'}
                        )
                        if order:
                            self._active_orders[order.id] = order
                            await self.db.insert_order(
                                self.bot_id, order.pair, order.id, order.side,
                                order.order_type, order.price, order.amount, order.metadata
                            )
                            print(f"[{self.bot_id}] MAKER ASK: {ask_size:.6f} @ ${ask_price:,.2f}")
                
                # Cancel stale orders (older than 30s or far from mid)
                for order in list(current_orders):
                    age = datetime.utcnow().timestamp() - order.created_at
                    if age > 30:  # Cancel after 30 seconds
                        await self.client.cancel_order(order.id)
                        self._active_orders.pop(order.id, None)
                        print(f"[{self.bot_id}] Cancelled stale order {order.id[:8]}")
                
                # Update stats
                await self._update_stats(mid, ob.best_bid, ob.best_ask, spread_bps)
                
                # Fast refresh
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.bot_id}] Error: {e}")
                await asyncio.sleep(2)
    
    def _calculate_amount(self, side: str, mid: float) -> float:
        """Calculate trade amount."""
        usd_amount = self.config.order_amount_usd
        return round(usd_amount / mid, 6)
    
    def _get_max_order_size(self, price: float) -> float:
        """Calculate max order size in base asset."""
        return round(100 / price, 6)  # $100 orders max
    
    def _get_max_position(self) -> float:
        """Get max position in base asset."""
        capital = 6000  # Total paper capital
        max_usd = capital * self.config.max_position_pct
        return max_usd / 100  # Rough estimate
    
    async def _update_stats(self, mid: float, bid: float, ask: float, spread_bps: float):
        """Update database stats."""
        try:
            await self.db.update_bot_status(
                self.bot_id, self.config.pair, self.is_running,
                bid, ask, mid, spread_bps, self.position,
                self.position * mid, 0.0, 0
            )
        except:
            pass
    
    async def _on_fill(self, fill: Fill):
        """Handle fill - ALWAYS print and log to DB."""
        print(f"\n*** ON_FILL CALLED for {self.bot_id} ***")
        
        if fill.bot_id != self.bot_id:
            print(f"*** WRONG BOT: expected {self.bot_id}, got {fill.bot_id} ***")
            return
        
        print(f"*** PROCESSING FILL: {fill.side} {fill.amount} @ {fill.price} ***")
        
        self.total_fills += 1
        self.last_trade_time = fill.timestamp
        
        # Update position tracking
        if fill.side == 'buy':
            self.position += fill.amount
        else:
            self.position -= fill.amount
        
        print(f"[{self.bot_id}] ✓ FILL #{self.total_fills}: {fill.side.upper()} {fill.amount:.6f} @ ${fill.price:.2f}")
        print(f"[{self.bot_id}] Position: {self.position:.6f} {self.config.pair.split('/')[0]}")
        
        # Get current balances for display
        try:
            usd_bal = self.client.get_balance('USD')['available']
            base_bal = self.client.get_balance(self.config.pair.split('/')[0])['available']
            print(f"[{self.bot_id}] Balance: ${usd_bal:.2f} USD, {base_bal:.6f} {self.config.pair.split('/')[0]}")
        except Exception as e:
            pass
        
        # Force DB insert with retry
        for attempt in range(3):
            try:
                success = await self.db.insert_fill(
                    fill.order_id, fill.fill_id, fill.bot_id,
                    fill.pair, fill.side, fill.price, fill.amount,
                    fill.fee, fill.fee_currency
                )
                if success:
                    print(f"[{self.bot_id}] DB: Fill logged")
                    break
                else:
                    print(f"[{self.bot_id}] DB: Retry {attempt+1}")
                    await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[{self.bot_id}] DB ERROR: {e}")
                await asyncio.sleep(0.5)
        
        # Update P&L
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            pnl = self.client.calculate_pnl(self.bot_id, self.config.pair)
            await self.db.update_pnl(
                self.bot_id, self.config.pair, today,
                realized_pnl=pnl['realized_pnl'],
                fees_paid=pnl['fees'],
                trade_count=1
            )
            print(f"[{self.bot_id}] PnL: Realized=${pnl['realized_pnl']:.2f}, Fees=${pnl['fees']:.2f}, Net=${pnl['net_pnl']:.2f}")
        except Exception as e:
            print(f"[{self.bot_id}] PnL ERROR: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot stats."""
        return {
            'bot_id': self.bot_id,
            'pair': self.config.pair,
            'is_running': self.is_running,
            'position': self.position,
            'total_fills': self.total_fills
        }
