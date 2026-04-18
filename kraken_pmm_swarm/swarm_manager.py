import asyncio
import logging
from database import FreqDB
from kraken_paper_client import RobustPaperKrakenClient
from profit_guard import ProfitGuard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SwarmManager:
    def __init__(self):
        self.db = FreqDB()
        self.guard = ProfitGuard(self.db)
        self.bots = {}
        self.pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        logger.info("🌐 SwarmManager + ProfitGuard started - Kimi full autonomy ON")

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
            logger.info(f"📊 SWARM STATUS | Bots: {len(self.bots)} | Unrealized PnL: {total_unrealized:.4f} | Active positions: {len(positions)}")
            
            await asyncio.sleep(60)  # report every minute

    async def shutdown(self):
        for bot in self.bots.values():
            bot.running = False
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
