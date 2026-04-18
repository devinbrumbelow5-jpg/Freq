#!/usr/bin/env python3
"""
CEO SWARM v1.0 - Active Trading Command Center
Unified multi-strategy trading with CEO oversight.
Deploys ONLY profitable strategies, shuts down losers fast.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager

# Import strategy modules
from run_scalper_v2 import MeanReversionScalper, ScalperConfig
from run_grid_maker import GridMaker, GridConfig


class CEOTrader:
    """CEO-controlled trading swarm - only runs what works."""
    
    def __init__(self):
        self.client = CoinbasePaperClient()
        self.db = DatabaseManager('./ceo_swarm.db')
        
        # Pairs to trade
        self.pairs = ['BTC/USD', 'ETH/USD', 'SOL/USD']
        
        # Active bots
        self.bots: Dict[str, any] = {}
        self.pnl_tracking: Dict[str, List[Tuple[str, float, float]]] = {}
        
        # Performance thresholds
        self.shutdown_threshold = -0.03  # -3% = shutdown
        self.profit_target = 0.02  # +2% = scale up
        
    async def start(self):
        """Start CEO trading operation."""
        print(f"[CEO] Starting trading operation at {datetime.now()}")
        print(f"[CEO] Pairs: {self.pairs}")
        print(f"[CEO] Mode: AGGRESSIVE PROFIT HUNTING")
        
        # Initialize client
        await self.client.connect()
        
        # Deploy scalper on ALL pairs (only profitable strategy currently)
        for pair in self.pairs:
            bot_id = f"scalper_{pair.replace('/', '_')}"
            config = ScalperConfig(
                pair=pair,
                order_size_usd=300,  # Increased from 250
                take_profit_pct=0.35,  # Slightly lower = more fills
                stop_loss_pct=0.55,
                max_positions=2
            )
            
            bot = MeanReversionScalper(bot_id, config, self.client, self.db)
            await bot.start()
            self.bots[bot_id] = bot
            self.pnl_tracking[bot_id] = []
            print(f"[CEO] DEPLOYED: {bot_id} on {pair}")
        
        # Start monitoring loop
        await self._monitor_loop()
    
    async def _monitor_loop(self):
        """CEO monitoring - kill losers, scale winners."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            
            total_pnl = 0.0
            status_lines = []
            
            for bot_id, bot in self.bots.items():
                pnl = bot.total_pnl if hasattr(bot, 'total_pnl') else 0
                positions = len(bot.positions) if hasattr(bot, 'positions') else 0
                total_pnl += pnl
                
                status = f"{bot_id}: PnL={pnl:.2%} Pos={positions}"
                status_lines.append(status)
                
                # Kill losers
                if pnl < self.shutdown_threshold:
                    print(f"[CEO] 🚨 SHUTTING DOWN {bot_id}: PnL {pnl:.2%} < threshold")
                    await bot.stop()
                    self.bots.pop(bot_id, None)
            
            print(f"[CEO] {datetime.now().strftime('%H:%M:%S')} | {' | '.join(status_lines)}")
            print(f"[CEO] TOTAL PNL: {total_pnl:.2%}")
            
            # Log to file
            with open('ceo_swarm.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()},{total_pnl:.6f}\n")


async def main():
    """CEO Trading Entry Point."""
    print("="*60)
    print("CEO SWARM v1.0 - ACTIVE TRADING MODE")
    print("Directive: Trade until profitable")
    print("="*60)
    
    trader = CEOTrader()
    
    try:
        await trader.start()
    except KeyboardInterrupt:
        print("\n[CEO] Shutting down...")
        for bot in trader.bots.values():
            await bot.stop()


if __name__ == '__main__':
    asyncio.run(main())
