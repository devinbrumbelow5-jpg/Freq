"""
Statistical Arbitrage Engine
Exploits price discrepancies across exchanges using real-time WebSocket data
No directional prediction - pure risk-free arbitrage capture
"""

import asyncio
import ccxt.pro as ccxt
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import time

@dataclass
class ArbOpportunity:
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_pct: float
    profit_usd: float

class StatArbEngine:
    """
    Cross-exchange statistical arbitrage.
    Captures genuine market inefficiencies with millisecond latency.
    """
    
    def __init__(self, pairs: list, min_spread_bps: float = 10.0):
        self.pairs = pairs
        self.min_spread_bps = min_spread_bps
        self.min_spread_pct = min_spread_bps / 10000
        
        # Initialize exchanges
        self.exchanges = {
            'coinbase': ccxt.coinbase({'enableRateLimit': True}),
            'kraken': ccxt.kraken({'enableRateLimit': True}),
            'binance_us': ccxt.binanceus({'enableRateLimit': True})
        }
        
        # Price data: exchange -> pair -> {bid, ask, timestamp}
        self.prices = defaultdict(dict)
        
        # Execution tracking
        self.opportunities = 0
        self.executed = 0
        self.realized_profit = 0.0
        
        # Paper balances for simulation
        self.balances = {
            'USD': 10000.0,
            'BTC': 0.0,
            'ETH': 0.0,
            'SOL': 0.0
        }
        
        self.trade_size_usd = 500  # $500 per arb
    
    async def start(self):
        """Start all exchange feeds and arb scanner."""
        print("=" * 70)
        print("STATISTICAL ARBITRAGE ENGINE")
        print("=" * 70)
        print(f"Pairs: {', '.join(self.pairs)}")
        print(f"Min spread: {self.min_spread_bps} bps ({self.min_spread_pct:.3f}%)")
        print(f"Exchanges: {', '.join(self.exchanges.keys())}")
        print(f"Trade size: ${self.trade_size_usd}")
        print("=" * 70)
        print()
        
        tasks = []
        
        # Start price feeds for each exchange
        for ex_name, exchange in self.exchanges.items():
            for pair in self.pairs:
                tasks.append(self._feed(ex_name, exchange, pair))
        
        # Start arbitrage scanner
        tasks.append(self._scan())
        
        # Start PnL reporter
        tasks.append(self._report())
        
        await asyncio.gather(*tasks)
    
    async def _feed(self, ex_name: str, exchange, pair: str):
        """Maintain real-time price feed from exchange."""
        ccxt_pair = pair.replace('/', '-')
        
        while True:
            try:
                ob = await exchange.watch_order_book(ccxt_pair)
                
                self.prices[ex_name][pair] = {
                    'bid': float(ob['bids'][0][0]) if ob['bids'] else None,
                    'ask': float(ob['asks'][0][0]) if ob['asks'] else None,
                    'bid_vol': float(ob['bids'][0][1]) if ob['bids'] else 0,
                    'ask_vol': float(ob['asks'][0][1]) if ob['asks'] else 0,
                    'ts': time.time()
                }
                
            except Exception as e:
                await asyncio.sleep(0.5)
    
    async def _scan(self):
        """Scan for arbitrage opportunities."""
        await asyncio.sleep(3)  # Wait for initial data
        
        while True:
            try:
                for pair in self.pairs:
                    await self._check_pair(pair)
                await asyncio.sleep(0.1)  # 100ms scan interval
                
            except Exception as e:
                await asyncio.sleep(0.5)
    
    async def _check_pair(self, pair: str):
        """Check for arbitrage on specific pair."""
        # Get all exchange prices for this pair
        exchanges_with_data = {}
        
        for ex_name, pairs in self.prices.items():
            if pair in pairs:
                data = pairs[pair]
                # Check data freshness (< 2 seconds old)
                if data['ts'] > time.time() - 2 and data['bid'] and data['ask']:
                    exchanges_with_data[ex_name] = data
        
        if len(exchanges_with_data) < 2:
            return
        
        # Find best bid (highest) and best ask (lowest)
        best_bid = max(exchanges_with_data.items(), key=lambda x: x[1]['bid'])
        best_ask = min(exchanges_with_data.items(), key=lambda x: x[1]['ask'])
        
        # Must be different exchanges
        if best_bid[0] == best_ask[0]:
            return
        
        # Calculate spread
        spread_bps = ((best_bid[1]['bid'] - best_ask[1]['ask']) / best_ask[1]['ask']) * 10000
        
        if spread_bps > self.min_spread_bps:
            self.opportunities += 1
            
            # Calculate profit
            amount = self.trade_size_usd / best_ask[1]['ask']
            gross_profit = amount * (best_bid[1]['bid'] - best_ask[1]['ask'])
            
            # Simulate fees (0.1% maker per exchange = 0.2% total)
            fees = self.trade_size_usd * 0.002
            net_profit = gross_profit - fees
            
            if net_profit > 0:
                await self._execute_arb(pair, best_ask, best_bid, amount, net_profit)
    
    async def _execute_arb(self, pair: str, buy_ex: Tuple, sell_ex: Tuple, 
                           amount: float, profit: float):
        """Simulate arbitrage execution."""
        self.executed += 1
        self.realized_profit += profit
        
        base = pair.split('/')[0]
        
        # Update balances
        self.balances['USD'] -= self.trade_size_usd
        self.balances[base] += amount
        self.balances[base] -= amount
        self.balances['USD'] += (self.trade_size_usd + profit)
        
        print(f"\n💰 ARBITRAGE EXECUTED #{self.executed}")
        print(f"   Pair: {pair}")
        print(f"   Buy:  {buy_ex[0].upper()} @ ${buy_ex[1]['ask']:.2f}")
        print(f"   Sell: {sell_ex[0].upper()} @ ${sell_ex[1]['bid']:.2f}")
        print(f"   Size: ${self.trade_size_usd:.2f}")
        print(f"   Profit: ${profit:.2f}")
        print(f"   Total PnL: ${self.realized_profit:.2f}")
    
    async def _report(self):
        """Periodic reporting."""
        while True:
            await asyncio.sleep(60)
            print(f"\n[{time.strftime('%H:%M:%S')}] "
                  f"Opportunities: {self.opportunities} | "
                  f"Executed: {self.executed} | "
                  f"Profit: ${self.realized_profit:.2f} | "
                  f"Balance: ${self.balances['USD']:.2f}")

async def main():
    engine = StatArbEngine(
        pairs=['BTC/USD', 'ETH/USD', 'SOL/USD'],
        min_spread_bps=15.0  # 0.15% minimum spread
    )
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        print("\n\nShutdown complete.")
        print(f"Final Profit: ${engine.realized_profit:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
