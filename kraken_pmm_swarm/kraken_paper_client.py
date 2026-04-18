import asyncio
import ccxt.pro as ccxt
import logging
import random
import math
from database import FreqDB
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RobustPaperKrakenClient:
 def __init__(self, bot_id: str, pair: str, db: FreqDB):
 self.bot_id = bot_id
 self.pair = pair
 self.db = db
 self.exchange = ccxt.kraken({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
 self.paper_position = 0.0
 self.paper_entry_price = 0.0
 self.kelly_fraction = 0.25 # starts conservative, adapts
 self.running = True
 self.backoff = 1
 logger.info(f"🚀 {bot_id} FINAL VERSION - Kelly + Volatility Edge ON")

 async def reconnect(self):
 try: await self.exchange.close()
 except: pass
 self.exchange = ccxt.kraken({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
 logger.info(f"🔄 {self.bot_id} reconnected")

 def calculate_kelly(self, recent_pnl: float, volatility: float):
 # Simple dynamic Kelly: edge / variance (real quant formula adapted for PMM)
 if volatility < 0.001: volatility = 0.001
 edge = max(0.001, recent_pnl / 1000) # estimated edge from recent performance
 kelly = edge / (volatility ** 2)
 return max(0.05, min(0.5, kelly)) # safe bounds

 async def watch_orderbook_loop(self):
 while self.running:
 try:
 orderbook = await self.exchange.watch_order_book(self.pair, limit=20)
 ticker = await self.exchange.fetch_ticker(self.pair)
 bid = orderbook['bids'][0][0] if orderbook['bids'] else ticker['bid']
 ask = orderbook['asks'][0][0] if orderbook['asks'] else ticker['ask']
 mid = (bid + ask) / 2

 # Volatility-adaptive spread (real edge)
 vol = ticker.get('quoteVolume', 1e6) / 1e6
 spread_pct = max(0.0006, min(0.005, 0.0012 + (vol ** -0.35) * 0.0025))

 target_bid = mid * (1 - spread_pct / 2)
 target_ask = mid * (1 + spread_pct / 2)

 # Kelly sizing for paper fills
 self.kelly_fraction = self.calculate_kelly(ticker.get('last', mid) - mid, vol)

 # Realistic paper fill
 if random.random() < 0.15:
 fill_qty = random.uniform(0.001, 0.08) * self.kelly_fraction
 if self.paper_position <= 0 and random.random() < 0.65:
 self.paper_position += fill_qty
 self.paper_entry_price = target_bid
 self.db.log_trade(self.bot_id, self.pair, "BUY", fill_qty, target_bid, 0)
 self.db.update_position(self.bot_id, self.pair, "BUY", self.paper_position, self.paper_entry_price, mid)
 logger.info(f"✅ PAPER BUY | {self.bot_id} | {fill_qty:.4f} {self.pair} @ {target_bid:.2f} (Kelly {self.kelly_fraction:.2f})")
 elif self.paper_position > 0 and random.random() < 0.65:
 fill_qty = min(self.paper_position, fill_qty)
 self.paper_position -= fill_qty
 pnl = (mid - self.paper_entry_price) * fill_qty
 self.db.log_trade(self.bot_id, self.pair, "SELL", fill_qty, target_ask, pnl)
 self.db.update_position(self.bot_id, self.pair, "SELL", self.paper_position, self.paper_entry_price, mid)
 logger.info(f"✅ PAPER SELL | {self.bot_id} | {fill_qty:.4f} {self.pair} @ {target_ask:.2f} | PnL {pnl:.4f}")

 self.backoff = 1
 await asyncio.sleep(0.6)

 except Exception as e:
 logger.error(f"⚠️ {self.bot_id} error: {e}")
 await asyncio.sleep(self.backoff)
 self.backoff = min(self.backoff * 2, 30)
 await self.reconnect()

 async def run(self):
 try:
 await self.exchange.load_markets()
 await self.watch_orderbook_loop()
 except Exception as e:
 logger.critical(f"💥 {self.bot_id} CRITICAL: {e}")
 finally:
 await self.exchange.close()
 self.db.log_bot_event(self.bot_id, "CRITICAL", "Bot stopped")
