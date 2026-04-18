import asyncio
import logging
from datetime import datetime
from database import FreqDB
from kraken_paper_client import RobustPaperKrakenClient, TAKER_FEE, SLIPPAGE
from profit_guard import ProfitGuard

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SwarmManager:
    def __init__(self):
        self.db = FreqDB()
        self.guard = ProfitGuard(self.db)
        self.bots = {}
        self.pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.exchange = None
        self.last_balance_update = 0
        logger.info("🌐 SwarmManager + ProfitGuard started - Kimi full autonomy ON")
        
        # Initialize exchange for balance fetching
        if CCXT_AVAILABLE:
            try:
                self.exchange = ccxt.kraken({
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                logger.info("✅ Exchange connection initialized for live balance fetching")
            except Exception as e:
                logger.warning(f"⚠️ Could not init exchange: {e}")

    async def fetch_and_store_balance(self):
        """Fetch real USDC balance from exchange and store in DB"""
        if not CCXT_AVAILABLE or self.exchange is None:
            return
        
        try:
            # Fetch balance from exchange
            balance = await self.exchange.fetch_balance()
            
            # Get USDC free balance
            usdc_balance = balance.get('USDC', {}).get('free', 0)
            
            # Also check USD
            if usdc_balance == 0:
                usdc_balance = balance.get('USD', {}).get('free', 0)
            
            # Also check USDT
            if usdc_balance == 0:
                usdc_balance = balance.get('USDT', {}).get('free', 0)
            
            balance_float = float(usdc_balance) if usdc_balance else 1000.0
            
            # Store in database
            conn = self.db.get_conn()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO balances (currency, balance, timestamp)
                    VALUES ('USDC', %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (currency) DO UPDATE
                    SET balance = EXCLUDED.balance,
                        timestamp = CURRENT_TIMESTAMP
                """, (balance_float,))
                conn.commit()
                logger.info(f"💰 Live balance stored: ${balance_float:.2f} USDC")
            finally:
                cur.close()
                self.db.put_conn(conn)
                
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch live balance: {e}")

    async def start_swarm(self):
        tasks = []
        for i, pair in enumerate(self.pairs):
            bot_id = f"pmm-{pair.replace('/', '')}-{i}"
            client = RobustPaperKrakenClient(bot_id, pair, self.db)
            self.bots[bot_id] = client
            tasks.append(asyncio.create_task(client.run()))
        
        # Kimi autonomous monitoring + ProfitGuard loop
        while True:
            await self.guard.run_guard_cycle()
            positions = self.db.get_active_positions()
            total_unrealized = sum(p['unrealized_pnl'] or 0 for p in positions)
            
            # Fetch and store live balance every 30 seconds
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_balance_update >= 30:
                await self.fetch_and_store_balance()
                self.last_balance_update = current_time
            
            logger.info(f"📊 SWARM STATUS | Bots: {len(self.bots)} | Unrealized PnL: ${total_unrealized:.4f} | Active positions: {len(positions)} | Fees: {TAKER_FEE*100:.2f}% + {SLIPPAGE*100:.2f}% slippage")
            
            await asyncio.sleep(60)  # report every minute

    async def shutdown(self):
        for bot in self.bots.values():
            bot.running = False
        if self.exchange:
            await self.exchange.close()
        self.db.close()

async def main():
    manager = SwarmManager()
    try:
        await manager.start_swarm()
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested")
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
