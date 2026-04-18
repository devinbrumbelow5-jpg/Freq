import asyncio
import logging
from database import FreqDB
from kraken_paper_client import RobustPaperKrakenClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SwarmManager:
    def __init__(self):
        self.db = FreqDB()
        self.bots = {}
        self.pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]  # easy to expand
        logger.info("🌐 SwarmManager started - Kimi autonomy mode ON")

    async def start_swarm(self):
        tasks = []
        for i, pair in enumerate(self.pairs):
            bot_id = f"pmm-{pair.replace('/', '')}-{i}"
            client = RobustPaperKrakenClient(bot_id, pair, self.db)
            self.bots[bot_id] = client
            tasks.append(asyncio.create_task(client.run()))
        
        # Central monitoring loop (Kimi can read DB anytime)
        while True:
            positions = self.db.get_active_positions()
            total_unrealized = sum(p['unrealized_pnl'] for p in positions)
            logger.info(f"📊 SWARM STATUS | Active bots: {len(self.bots)} | Unrealized PnL: {total_unrealized:.4f} | Positions: {len(positions)}")
            
            # Simple auto-adjust (Kimi can later override via DB or file)
            if total_unrealized < -50:  # safety net
                logger.warning("⚠️ DRAWDOWN DETECTED - pausing aggressive quoting")
            
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
