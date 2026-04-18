import asyncio
import ccxt.pro as ccxt
import logging
import random
from database import FreqDB
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fee and slippage constants
TAKER_FEE = 0.0026
SLIPPAGE = 0.0005
SINGLE_LEG_COST = TAKER_FEE + SLIPPAGE  # 0.31%
NET_FACTOR = 1 - SINGLE_LEG_COST        # 0.9969

def apply_entry_fee(price):
    """Apply entry fee + slippage to price (worse price for buyer)"""
    return price * (1 + SINGLE_LEG_COST)

def apply_exit_fee(price):
    """Apply exit fee + slippage to price (worse price for seller)"""
    return price * (1 - SINGLE_LEG_COST)

def calculate_net_pnl(gross_pnl, entry_price, exit_price, qty):
    """Calculate net PnL after fees and slippage"""
    entry_cost = entry_price * qty * SINGLE_LEG_COST
    exit_cost = exit_price * qty * SINGLE_LEG_COST
    return gross_pnl - entry_cost - exit_cost

class RobustPaperKrakenClient:
    def __init__(self, bot_id: str, pair: str, db: FreqDB):
        self.bot_id = bot_id
        self.pair = pair
        self.db = db
        self.exchange = ccxt.kraken({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
        self.paper_position = 0.0
        self.paper_entry_price = 0.0
        self.kelly_fraction = 0.25
        self.running = True
        self.backoff = 1
        self.total_fees_paid = 0.0
        logger.info(f"🚀 {bot_id} FINAL VERSION - Kelly + Volatility Edge ON")

    async def reconnect(self):
        try:
            await self.exchange.close()
        except:
            pass
        self.exchange = ccxt.kraken({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
        logger.info(f"🔄 {self.bot_id} reconnected")

    def calculate_kelly(self, recent_pnl: float, volatility: float):
        if volatility < 0.001:
            volatility = 0.001
        edge = max(0.001, recent_pnl / 1000)
        kelly = edge / (volatility ** 2)
        return max(0.05, min(0.5, kelly))

    async def watch_orderbook_loop(self):
        while self.running:
            try:
                orderbook = await self.exchange.watch_order_book(self.pair, limit=10)
                ticker = await self.exchange.fetch_ticker(self.pair)
                bid = orderbook['bids'][0][0] if orderbook['bids'] else ticker['bid']
                ask = orderbook['asks'][0][0] if orderbook['asks'] else ticker['ask']
                mid = (bid + ask) / 2

                vol = ticker.get('quoteVolume', 1e6) / 1e6
                spread_pct = max(0.0006, min(0.005, 0.0012 + (vol ** -0.35) * 0.0025))

                target_bid = mid * (1 - spread_pct / 2)
                target_ask = mid * (1 + spread_pct / 2)

                self.kelly_fraction = self.calculate_kelly(ticker.get('last', mid) - mid, vol)

                if random.random() < 0.15:
                    fill_qty = random.uniform(0.001, 0.08) * self.kelly_fraction
                    if self.paper_position <= 0 and random.random() < 0.65:
                        entry_price_with_fees = apply_entry_fee(target_bid)
                        self.paper_position += fill_qty
                        self.paper_entry_price = target_bid
                        entry_fee_amount = (entry_price_with_fees - target_bid) * fill_qty
                        self.total_fees_paid += entry_fee_amount
                        # Log trade at net price (with fees)
                        self.db.log_trade(self.bot_id, self.pair, "BUY", fill_qty, entry_price_with_fees, 0)
                        # Update position with net entry price
                        self.db.update_position(self.bot_id, self.pair, "BUY", self.paper_position, 
                                               entry_price_with_fees, apply_exit_fee(mid))
                        logger.info(f"✅ PAPER BUY | {self.bot_id} | {fill_qty:.4f} {self.pair} @ {target_bid:.2f} (net: {entry_price_with_fees:.2f}) | Fees: {entry_fee_amount:.4f}")
                    elif self.paper_position > 0 and random.random() < 0.65:
                        fill_qty = min(self.paper_position, fill_qty)
                        exit_price_with_fees = apply_exit_fee(target_ask)
                        # Gross PnL (before fees)
                        gross_pnl = (target_ask - self.paper_entry_price) * fill_qty
                        # Net PnL (after fees)
                        net_pnl = calculate_net_pnl(gross_pnl, self.paper_entry_price, target_ask, fill_qty)
                        exit_fee_amount = (target_ask - exit_price_with_fees) * fill_qty
                        self.total_fees_paid += exit_fee_amount
                        self.paper_position -= fill_qty
                        # Log trade with NET PnL
                        self.db.log_trade(self.bot_id, self.pair, "SELL", fill_qty, exit_price_with_fees, net_pnl)
                        # Update position with net current price
                        self.db.update_position(self.bot_id, self.pair, "SELL", self.paper_position, 
                                               self.paper_entry_price, exit_price_with_fees)
                        logger.info(f"✅ PAPER SELL | {self.bot_id} | {fill_qty:.4f} {self.pair} @ {target_ask:.2f} (net: {exit_price_with_fees:.2f}) | Gross PnL: {gross_pnl:.4f} | Net PnL: {net_pnl:.4f}")

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
