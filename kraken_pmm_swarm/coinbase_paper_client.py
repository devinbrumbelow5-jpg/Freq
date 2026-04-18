"""
Coinbase Paper Trading Client - CCXT Pro WebSocket wrapper with paper trading simulation.
Uses real Coinbase WebSocket data, simulates order execution and balance tracking.
"""

import ccxt.pro as ccxt
import asyncio
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid


@dataclass
class Order:
    """Paper trading order."""
    id: str
    bot_id: str
    pair: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'limit' or 'market'
    price: float
    amount: float
    filled: float = 0.0
    status: str = 'open'  # open, filled, partial, cancelled, expired
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    metadata: Dict = field(default_factory=dict)


@dataclass
class Fill:
    """Paper trading fill."""
    fill_id: str
    order_id: str
    bot_id: str
    pair: str
    side: str
    price: float
    amount: float
    fee: float
    fee_currency: str
    timestamp: float
    metadata: Dict = field(default_factory=dict)  # Added metadata for PnL tracking


@dataclass
class OrderBook:
    """L2 order book snapshot."""
    pair: str
    bids: List[List[float]] = field(default_factory=list)  # [[price, amount], ...]
    asks: List[List[float]] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0][0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0][0] if self.asks else None
    
    @property
    def mid_price(self) -> Optional[float]:
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return (bb + ba) / 2
        return None
    
    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if not mid or not self.best_bid or not self.best_ask:
            return 0.0
        return ((self.best_ask - self.best_bid) / mid) * 10000


class CoinbasePaperClient:
    """
    Coinbase client with paper trading simulation.
    Uses CCXT Pro for real WebSocket data, simulates orders and balances.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 paper_balances: Dict[str, float] = None,
                 max_slippage_pct: float = 0.05):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.paper_balances = paper_balances.copy() if paper_balances else {'USDT': 100000}
        self.initial_balances = self.paper_balances.copy()
        self.max_slippage_pct = max_slippage_pct
        
        # Coinbase has public WebSocket - no auth needed for market data
        self.exchange = ccxt.coinbase({
            'enableRateLimit': True,
        })
        
        # Paper trading state
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.order_books: Dict[str, OrderBook] = {}
        self.positions: Dict[str, float] = {}
        
        # Async state
        self._running = False
        self._ws_tasks: List[asyncio.Task] = []
        self._watch_pairs: set = set()
        self._lock = asyncio.Lock()
        
        # Callbacks - Dictionary keyed by bot_id for multi-bot routing
        self.on_fill_callbacks: Dict[str, Callable[[Fill], Any]] = {}
        self.on_order_update: Optional[Callable[[Order], Any]] = None
        
        # Legacy callback (deprecated, use on_fill_callbacks)
        self._on_fill_legacy: Optional[Callable[[Fill], Any]] = None
    
    @property
    def on_fill(self) -> Optional[Callable[[Fill], Any]]:
        """Get legacy on_fill callback."""
        return self._on_fill_legacy
    
    @on_fill.setter  
    def on_fill(self, callback: Callable[[Fill], Any]):
        """Set legacy on_fill callback (used by single-bot setups)."""
        self._on_fill_legacy = callback
    
    def register_fill_callback(self, bot_id: str, callback: Callable[[Fill], Any]):
        """Register a fill callback for a specific bot."""
        self.on_fill_callbacks[bot_id] = callback
        print(f"[CLIENT] Registered fill callback for {bot_id}")
    
    def unregister_fill_callback(self, bot_id: str):
        """Unregister a fill callback for a specific bot."""
        if bot_id in self.on_fill_callbacks:
            del self.on_fill_callbacks[bot_id]
            print(f"[CLIENT] Unregistered fill callback for {bot_id}")
    
    async def start(self, pairs: List[str]):
        """Start WebSocket connections for specified pairs."""
        self._running = True
        self._watch_pairs = set(pairs)
        
        # Start order book watchers for each pair
        for pair in pairs:
            task = asyncio.create_task(self._watch_order_book(pair))
            self._ws_tasks.append(task)
        
        # Start order matching engine
        task = asyncio.create_task(self._matching_engine())
        self._ws_tasks.append(task)
    
    async def stop(self):
        """Stop all WebSocket connections."""
        self._running = False
        for task in self._ws_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._ws_tasks.clear()
        await self.exchange.close()
    
    async def _watch_order_book(self, pair: str):
        """WebSocket order book watcher with auto-reconnect."""
        # Coinbase uses BTC-USD format
        ccxt_pair = pair.replace('/', '-')
        reconnect_delay = 1.0
        max_reconnect = 60.0
        
        while self._running:
            try:
                orderbook = await self.exchange.watch_order_book(ccxt_pair)
                bids = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:10]]
                asks = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:10]]
                
                self.order_books[pair] = OrderBook(
                    pair=pair,
                    bids=bids,
                    asks=asks
                )
                reconnect_delay = 1.0
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Order book error for {pair}: {str(e)[:60]}")
                await asyncio.sleep(min(reconnect_delay, max_reconnect))
                reconnect_delay *= 1.5
    
    async def _matching_engine(self):
        """Match paper orders against real order book."""
        while self._running:
            try:
                async with self._lock:
                    for order in list(self.orders.values()):
                        if order.status not in ['open', 'partial']:
                            continue
                        
                        ob = self.order_books.get(order.pair)
                        if not ob or not ob.best_bid or not ob.best_ask:
                            continue
                        
                        fill_price = None
                        
                        if order.side == 'buy' and order.order_type == 'limit':
                            # MAKER BUY: Order rests below ask, fills when bid rises to our price
                            # OR if price >= ask (aggressive fill)
                            print(f"[MATCH DEBUG] BUY checking: price {order.price} >= ask {ob.best_ask} OR bid {ob.best_bid} >= price {order.price}?")
                            if order.price >= ob.best_ask:
                                # Aggressive fill - crossed spread
                                fill_price = order.price
                                print(f"[MATCH] Filling BUY order {order.id[:8]} AGGRESSIVELY at {fill_price:.2f}")
                            elif ob.best_bid >= order.price:
                                # Maker fill - someone hit our bid
                                fill_price = order.price
                                print(f"[MATCH] Filling BUY order {order.id[:8]} MAKER at {fill_price:.2f}")
                            else:
                                print(f"[MATCH] BUY order {order.id[:8]}: price {order.price:.2f}, bid {ob.best_bid:.2f}, ask {ob.best_ask:.2f}")
                                continue
                            try:
                                await self._execute_fill(order, fill_price)
                                print(f"[MATCH] BUY fill completed")
                            except Exception as e:
                                print(f"[MATCH ERROR] BUY fill failed: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        elif order.side == 'sell' and order.order_type == 'limit':
                            # MAKER SELL: Order rests above bid, fills when ask drops to our price
                            # OR if price <= bid (aggressive fill)
                            print(f"[MATCH DEBUG] SELL checking: price {order.price} <= bid {ob.best_bid} OR ask {ob.best_ask} <= price {order.price}?")
                            if order.price <= ob.best_bid:
                                # Aggressive fill - crossed spread
                                fill_price = order.price
                                print(f"[MATCH] Filling SELL order {order.id[:8]} AGGRESSIVELY at {fill_price:.2f}")
                            elif ob.best_ask <= order.price:
                                # Maker fill - someone took our ask
                                fill_price = order.price
                                print(f"[MATCH] Filling SELL order {order.id[:8]} MAKER at {fill_price:.2f}")
                            else:
                                print(f"[MATCH] SELL order {order.id[:8]}: price {order.price:.2f}, bid {ob.best_bid:.2f}, ask {ob.best_ask:.2f}")
                                continue
                            try:
                                await self._execute_fill(order, fill_price)
                                print(f"[MATCH] SELL fill completed")
                            except Exception as e:
                                print(f"[MATCH ERROR] SELL fill failed: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        elif order.order_type == 'market':
                            fill_price = ob.best_ask if order.side == 'buy' else ob.best_bid
                            await self._execute_fill(order, fill_price)
                
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Matching engine error: {e}")
                await asyncio.sleep(0.5)
    
    async def _execute_fill(self, order: Order, fill_price: float):
        """Execute a paper fill and update balances."""
        print(f"[_EXECUTE_FILL] === ENTERED === order={order.id[:8]}, price={fill_price}")
        remaining = order.amount - order.filled
        fill_amount = remaining
        
        # Maker rebate: 0% fee for maker orders (was 0.5% taker)
        fee_rate = 0.0
        fill_value = fill_amount * fill_price
        fee = fill_value * fee_rate
        
        base, quote = order.pair.split('/')
        print(f"[_EXECUTE_FILL] base={base}, quote={quote}, amount={fill_amount}, fee={fee} (MAKER REBATE)")
        
        # Execute fill without lock - matching engine already holds lock context
        print(f"[_EXECUTE_FILL] Executing fill without nested lock")
        try:
            if order.side == 'buy':
                self.paper_balances[quote] = self.paper_balances.get(quote, 0) - fill_value - fee
                self.paper_balances[base] = self.paper_balances.get(base, 0) + fill_amount
                self.positions[order.pair] = self.positions.get(order.pair, 0) + fill_amount
            else:
                self.paper_balances[base] = self.paper_balances.get(base, 0) - fill_amount
                self.paper_balances[quote] = self.paper_balances.get(quote, 0) + fill_value - fee
                self.positions[order.pair] = self.positions.get(order.pair, 0) - fill_amount
            
            fill = Fill(
                fill_id=str(uuid.uuid4()),
                order_id=order.id,
                bot_id=order.bot_id,
                pair=order.pair,
                side=order.side,
                price=fill_price,
                amount=fill_amount,
                fee=fee,
                fee_currency=quote,
                timestamp=datetime.utcnow().timestamp(),
                metadata=order.metadata.copy()  # Pass order metadata to fill
            )
            self.fills.append(fill)
            print(f"[_EXECUTE_FILL] Fill recorded: {fill.fill_id[:8]}, total fills: {len(self.fills)}")
            
            order.filled += fill_amount
            order.status = 'filled' if order.filled >= order.amount else 'partial'
            print(f"[_EXECUTE_FILL] Order status: {order.status}, filled: {order.filled}/{order.amount}")
            
            # Notify callbacks - Route to correct bot via bot_id
            callback = self.on_fill_callbacks.get(order.bot_id)
            print(f"[EXECUTE_FILL] Looking for callback for {order.bot_id}: {callback is not None}")
            if callback:
                print(f"[EXECUTE_FILL] Calling registered callback for {order.bot_id}")
                asyncio.create_task(self._safe_callback(callback, fill))
            elif self.on_fill:
                # Fallback to legacy callback
                print(f"[EXECUTE_FILL] Fallback to legacy on_fill for {order.bot_id}")
                asyncio.create_task(self._safe_callback(self.on_fill, fill))
            else:
                print(f"[EXECUTE_FILL] WARNING: No callback found for {order.bot_id}!")
            if self.on_order_update:
                asyncio.create_task(self._safe_callback(self.on_order_update, order))
                
        except Exception as e:
            print(f"[_EXECUTE_FILL ERROR] {e}")
            import traceback
            traceback.print_exc()
    
    async def _safe_callback(self, callback, *args):
        """Safely execute callback."""
        try:
            print(f"[CALLBACK] Executing {callback.__name__ if hasattr(callback, '__name__') else 'callback'}")
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
            print(f"[CALLBACK] Success")
        except Exception as e:
            print(f"[CALLBACK ERROR] {e}")
            import traceback
            traceback.print_exc()
    
    async def create_limit_order(self, bot_id: str, pair: str, side: str, 
                                price: float, amount: float,
                                metadata: Optional[Dict] = None) -> Optional[Order]:
        """Create a paper limit order."""
        base, quote = pair.split('/')
        
        async with self._lock:
            if side == 'buy':
                required = price * amount
                available = self.paper_balances.get(quote, 0)
                if available < required:
                    print(f"Insufficient {quote} balance: {available:.2f} < {required:.2f}")
                    return None
            else:
                available = self.paper_balances.get(base, 0)
                if available < amount:
                    print(f"Insufficient {base} balance: {available:.6f} < {amount:.6f}")
                    return None
            
            order = Order(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                pair=pair,
                side=side,
                order_type='limit',
                price=price,
                amount=amount,
                metadata=metadata or {}
            )
            self.orders[order.id] = order
            
            if side == 'buy':
                self.paper_balances[quote] -= price * amount
            else:
                self.paper_balances[base] -= amount
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order."""
        async with self._lock:
            order = self.orders.get(order_id)
            if not order or order.status not in ['open', 'partial']:
                return False
            
            base, quote = order.pair.split('/')
            remaining = order.amount - order.filled
            
            if order.side == 'buy':
                self.paper_balances[quote] += order.price * remaining
            else:
                self.paper_balances[base] += remaining
            
            order.status = 'cancelled'
            
            if self.on_order_update:
                asyncio.create_task(self._safe_callback(self.on_order_update, order))
            
            return True
    
    async def cancel_all_orders(self, bot_id: str) -> int:
        """Cancel all orders for a bot."""
        cancelled = 0
        for order in list(self.orders.values()):
            if order.bot_id == bot_id and order.status in ['open', 'partial']:
                if await self.cancel_order(order.id):
                    cancelled += 1
        return cancelled
    
    def get_order_book(self, pair: str) -> Optional[OrderBook]:
        return self.order_books.get(pair)
    
    def get_balance(self, currency: str) -> Dict[str, float]:
        return {
            'available': self.paper_balances.get(currency, 0.0),
            'total': self.paper_balances.get(currency, 0.0),
            'reserved': 0.0
        }
    
    def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        result = {}
        for curr in self.initial_balances.keys():
            result[curr] = self.get_balance(curr)
        return result
    
    def get_position(self, pair: str) -> float:
        return self.positions.get(pair, 0.0)
    
    def get_orders(self, bot_id: Optional[str] = None, 
                   status: Optional[str] = None) -> List[Order]:
        result = []
        for order in self.orders.values():
            if bot_id and order.bot_id != bot_id:
                continue
            if status and order.status != status:
                continue
            result.append(order)
        return result
    
    def get_fills(self, bot_id: Optional[str] = None, 
                  since: Optional[float] = None) -> List[Fill]:
        result = []
        for fill in reversed(self.fills):
            if bot_id and fill.bot_id != bot_id:
                continue
            if since and fill.timestamp < since:
                continue
            result.append(fill)
        return result
    
    def calculate_pnl(self, bot_id: str, pair: str) -> Dict[str, float]:
        fills = [f for f in self.fills if f.bot_id == bot_id and f.pair == pair]
        
        realized_pnl = 0.0
        fees = 0.0
        buy_queue = []
        
        for fill in fills:
            if fill.side == 'buy':
                buy_queue.append((fill.amount, fill.price))
                fees += fill.fee
            else:
                sell_amount = fill.amount
                sell_price = fill.price
                
                while sell_amount > 0 and buy_queue:
                    buy_amount, buy_price = buy_queue[0]
                    matched = min(sell_amount, buy_amount)
                    
                    pnl = matched * (sell_price - buy_price)
                    realized_pnl += pnl
                    
                    sell_amount -= matched
                    buy_queue[0] = (buy_amount - matched, buy_price)
                    if buy_queue[0][0] <= 0:
                        buy_queue.pop(0)
                
                fees += fill.fee
        
        return {
            'realized_pnl': realized_pnl,
            'fees': fees,
            'net_pnl': realized_pnl - fees,
            'unrealized_pnl': 0.0,
            'fill_count': len(fills)
        }
