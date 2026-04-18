"""
Kraken Paper Trading Client - CCXT Pro WebSocket wrapper with paper trading simulation.
Uses real Kraken WebSocket data, simulates order execution and balance tracking.
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


class KrakenPaperClient:
    """
    Kraken client with paper trading simulation.
    Uses CCXT Pro for real WebSocket data, simulates orders and balances.
    """
    
    def __init__(self, api_key: str, api_secret: str, 
                 paper_balances: Dict[str, float],
                 max_slippage_pct: float = 0.05):
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper_balances = paper_balances.copy()
        self.initial_balances = paper_balances.copy()
        self.max_slippage_pct = max_slippage_pct
        
        # Real exchange for market data
        self.exchange = ccxt.kraken({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        # Paper trading state
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.order_books: Dict[str, OrderBook] = {}
        self.positions: Dict[str, float] = {}  # pair -> net position (base asset)
        
        # Callbacks
        self.on_fill: Optional[Callable[[Fill], Any]] = None
        self.on_order_update: Optional[Callable[[Order], Any]] = None
        
        # Async state
        self._running = False
        self._ws_tasks: List[asyncio.Task] = []
        self._watch_pairs: set = set()
        self._lock = asyncio.Lock()
    
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
        ccxt_pair = pair.replace('/', '/')
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
                reconnect_delay = 1.0  # Reset on success
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Order book error for {pair}: {str(e)[:60]}")
                await asyncio.sleep(min(reconnect_delay, max_reconnect))
                reconnect_delay *= 1.5  # Exponential backoff
    
    async def _matching_engine(self):
        """Match paper orders against real order book."""
        import random
        while self._running:
            try:
                async with self._lock:
                    for order in list(self.orders.values()):
                        if order.status not in ['open', 'partial']:
                            continue
                        
                        ob = self.order_books.get(order.pair)
                        if not ob or not ob.best_bid or not ob.best_ask:
                            continue
                        
                        # Check if order would fill
                        fill_price = None
                        
                        if order.side == 'buy' and order.order_type == 'limit':
                            # Buy limit fills if our bid is >= best ask (crossing)
                            # OR if we get lucky and someone hits our bid
                            if order.price >= ob.best_ask:
                                # Crossed spread - fill immediately
                                fill_price = self._calculate_fill_price(order, ob, 'buy')
                            elif order.price >= ob.best_bid:
                                # Passive fill: 5% chance per cycle if we're best bid
                                if random.random() < 0.05 and order.price == max(ob.bids[0][0] for _ in [0]):
                                    fill_price = order.price
                        
                        elif order.side == 'sell' and order.order_type == 'limit':
                            # Sell limit fills if our ask is <= best bid (crossing)
                            # OR if we get lucky
                            if order.price <= ob.best_bid:
                                # Crossed spread - fill immediately
                                fill_price = self._calculate_fill_price(order, ob, 'sell')
                            elif order.price <= ob.best_ask:
                                # Passive fill: 5% chance per cycle
                                if random.random() < 0.05 and order.price == min(ob.asks[0][0] for _ in [0]):
                                    fill_price = order.price
                        
                        elif order.order_type == 'market':
                            # Market orders fill immediately at spread-crossing price
                            fill_price = ob.best_ask if order.side == 'buy' else ob.best_bid
                        
                        if fill_price:
                            await self._execute_fill(order, fill_price)
                
                await asyncio.sleep(0.1)  # 100ms matching cycle
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Matching engine error: {e}")
                await asyncio.sleep(0.5)
    
    def _calculate_fill_price(self, order: Order, ob: OrderBook, side: str) -> float:
        """Calculate realistic fill price with slippage simulation."""
        if side == 'buy':
            # Buy at ask + small slippage
            base_price = ob.best_ask
            slippage = base_price * (self.max_slippage_pct / 100)
            return base_price + slippage
        else:
            # Sell at bid - small slippage
            base_price = ob.best_bid
            slippage = base_price * (self.max_slippage_pct / 100)
            return base_price - slippage
    
    async def _execute_fill(self, order: Order, fill_price: float):
        """Execute a paper fill and update balances."""
        remaining = order.amount - order.filled
        fill_amount = remaining  # Simplified: fill entire remaining amount
        
        # Calculate fee (0.16% taker for Kraken)
        fee_rate = 0.0016
        fill_value = fill_amount * fill_price
        fee = fill_value * fee_rate
        
        base, quote = order.pair.split('/')
        
        async with self._lock:
            # Update balances
            if order.side == 'buy':
                # Deduct quote, add base
                self.paper_balances[quote] = self.paper_balances.get(quote, 0) - fill_value - fee
                self.paper_balances[base] = self.paper_balances.get(base, 0) + fill_amount
                self.positions[order.pair] = self.positions.get(order.pair, 0) + fill_amount
            else:  # sell
                # Deduct base, add quote
                self.paper_balances[base] = self.paper_balances.get(base, 0) - fill_amount
                self.paper_balances[quote] = self.paper_balances.get(quote, 0) + fill_value - fee
                self.positions[order.pair] = self.positions.get(order.pair, 0) - fill_amount
            
            # Create fill record
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
                timestamp=datetime.utcnow().timestamp()
            )
            self.fills.append(fill)
            
            # Update order
            order.filled += fill_amount
            order.status = 'filled' if order.filled >= order.amount else 'partial'
        
        # Notify callbacks
        if self.on_fill:
            asyncio.create_task(self._safe_callback(self.on_fill, fill))
        if self.on_order_update:
            asyncio.create_task(self._safe_callback(self.on_order_update, order))
    
    async def _safe_callback(self, callback, *args):
        """Safely execute callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            print(f"Callback error: {e}")
    
    async def create_limit_order(self, bot_id: str, pair: str, side: str, 
                                price: float, amount: float,
                                metadata: Optional[Dict] = None) -> Optional[Order]:
        """Create a paper limit order."""
        base, quote = pair.split('/')
        
        async with self._lock:
            # Check balance
            if side == 'buy':
                required = price * amount
                available = self.paper_balances.get(quote, 0)
                if available < required:
                    print(f"Insufficient {quote} balance: {available} < {required}")
                    return None
            else:
                available = self.paper_balances.get(base, 0)
                if available < amount:
                    print(f"Insufficient {base} balance: {available} < {amount}")
                    return None
            
            # Create order
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
            
            # Reserve balance
            if side == 'buy':
                self.paper_balances[quote] -= price * amount
            else:
                self.paper_balances[base] -= amount
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order and return reserved funds."""
        async with self._lock:
            order = self.orders.get(order_id)
            if not order or order.status not in ['open', 'partial']:
                return False
            
            base, quote = order.pair.split('/')
            remaining = order.amount - order.filled
            
            # Return reserved funds
            if order.side == 'buy':
                self.paper_balances[quote] += order.price * remaining
            else:
                self.paper_balances[base] += remaining
            
            order.status = 'cancelled'
            
            if self.on_order_update:
                asyncio.create_task(self._safe_callback(self.on_order_update, order))
            
            return True
    
    async def cancel_all_orders(self, bot_id: str) -> int:
        """Cancel all orders for a bot. Returns count cancelled."""
        cancelled = 0
        for order in list(self.orders.values()):
            if order.bot_id == bot_id and order.status in ['open', 'partial']:
                if await self.cancel_order(order.id):
                    cancelled += 1
        return cancelled
    
    def get_order_book(self, pair: str) -> Optional[OrderBook]:
        """Get current order book for a pair."""
        return self.order_books.get(pair)
    
    def get_balance(self, currency: str) -> Dict[str, float]:
        """Get paper balance for a currency."""
        return {
            'available': self.paper_balances.get(currency, 0.0),
            'total': self.paper_balances.get(currency, 0.0),
            'reserved': 0.0  # Simplified
        }
    
    def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """Get all paper balances."""
        result = {}
        for curr in self.initial_balances.keys():
            result[curr] = self.get_balance(curr)
        return result
    
    def get_position(self, pair: str) -> float:
        """Get net position for a pair."""
        return self.positions.get(pair, 0.0)
    
    def get_orders(self, bot_id: Optional[str] = None, 
                   status: Optional[str] = None) -> List[Order]:
        """Get orders, optionally filtered."""
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
        """Get fills, optionally filtered."""
        result = []
        for fill in reversed(self.fills):  # Most recent first
            if bot_id and fill.bot_id != bot_id:
                continue
            if since and fill.timestamp < since:
                continue
            result.append(fill)
        return result
    
    def calculate_pnl(self, bot_id: str, pair: str) -> Dict[str, float]:
        """Calculate realized PnL for a bot/pair."""
        fills = [f for f in self.fills if f.bot_id == bot_id and f.pair == pair]
        
        realized_pnl = 0.0
        fees = 0.0
        
        # Simple FIFO PnL calculation
        buy_queue = []
        for fill in fills:
            if fill.side == 'buy':
                buy_queue.append((fill.amount, fill.price))
                fees += fill.fee
            else:  # sell
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
            'unrealized_pnl': 0.0,  # Would need mark price
            'fill_count': len(fills)
        }
