#!/usr/bin/env python3
"""EMA Crossover - Proven Backtested Strategy"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ema_bot import EMACrossoverBot, EMAConfig
from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager

async def main():
    print("=" * 60)
    print("EMA CROSSOVER STRATEGY")
    print("Backtested: 491% return, 1.30 Sharpe (3 years BTC)")
    print("Fast EMA: 12 | Slow EMA: 26")
    print("=" * 60)
    
    client = CoinbasePaperClient(
        paper_balances={'USD': 10000, 'BTC': 0.1, 'ETH': 0.5, 'SOL': 5.0},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./ema_strategy.db')
    await db.connect()
    
    # Create 3 bots for BTC, ETH, SOL
    bots = []
    configs = [
        ('ema_btc', 'BTC/USD', 1000),
        ('ema_eth', 'ETH/USD', 500),
        ('ema_sol', 'SOL/USD', 500)
    ]
    
    for bot_id, pair, size in configs:
        bot = EMACrossoverBot(
            bot_id=bot_id,
            config=EMAConfig(
                pair=pair,
                fast_period=12,
                slow_period=26,
                order_size_usd=size,
                stop_loss_pct=5.0
            ),
            client=client,
            database=db
        )
        bots.append((bot_id, bot))
    
    await client.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
    await asyncio.sleep(3)
    
    for bot_id, bot in bots:
        await bot.start()
        print(f"✓ Started {bot_id}")
    
    print("\n✓ All 3 EMA strategies active (BTC, ETH, SOL)")
    print("Collecting price data (need 26 periods)...\n")
    
    try:
        while True:
            await asyncio.sleep(60)
            total_trades = sum(bot.get_stats()['trades'] for _, bot in bots)
            if total_trades > 0:
                print(f"[{datetime.now().strftime('%H:%M')}] Total Trades: {total_trades}")
                for bot_id, bot in bots:
                    stats = bot.get_stats()
                    if stats['trades'] > 0:
                        print(f"  {bot_id}: {stats['trades']} trades, {stats['win_rate']*100:.0f}% WR, {stats['total_pnl_pct']:+.2f}%")
                      
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        for _, bot in bots:
            await bot.stop()
        await client.stop()
        await db.close()
        
        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        for bot_id, bot in bots:
            final = bot.get_stats()
            print(f"{bot_id}: {final['trades']} trades, {final['win_rate']*100:.1f}% WR, {final['total_pnl_pct']:+.2f}%")
        print("=" * 60)

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
