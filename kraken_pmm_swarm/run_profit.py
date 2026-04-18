#!/usr/bin/env python3
"""
Profitable Trading Bot - Bollinger Band Mean Reversion
Only trades at statistical extremes with strict stops
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bollinger_bot import BollingerBot, BBConfig
from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager


async def main():
    print("=" * 60)
    print("BOLLINGER BAND MEAN REVERSION BOT")
    print("Strategy: Buy at lower band, sell at mean")
    print("Risk: 1% stop loss, 0.5% take profit")
    print("=" * 60)
    
    # Initialize with conservative capital
    client = CoinbasePaperClient(
        paper_balances={'USD': 5000, 'BTC': 0.05, 'ETH': 0.5},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./profits_bollinger.db')
    await db.connect()
    
    # Create bot for BTC with conservative settings
    bot = BollingerBot(
        bot_id='bb_btc',
        config=BBConfig(
            pair='BTC/USD',
            period=20,
            std_dev=2.0,
            order_size_usd=500,  # $500 per trade
            stop_loss_pct=1.0,   # 1% max loss
            take_profit_pct=0.5  # 0.5% target
        ),
        client=client,
        database=db
    )
    
    # Start market data
    await client.start(['BTC/USD'])
    await asyncio.sleep(3)  # Wait for initial data
    
    # Start bot
    await bot.start()
    print("\n✓ Bot started. Monitoring BTC/USD...")
    
    try:
        while True:
            await asyncio.sleep(60)
            stats = bot.get_stats()
            print(f"[{datetime.now().strftime('%H:%M')}] "
                  f"Trades: {stats['trades']} | "
                  f"Win Rate: {stats['win_rate']*100:.1f}% | "
                  f"PnL: ${stats['total_pnl']:.2f}")
                  
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        await bot.stop()
        await client.stop()
        await db.close()
        
        final = bot.get_stats()
        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        print(f"Total Trades: {final['trades']}")
        print(f"Wins: {final['wins']} | Losses: {final['losses']}")
        print(f"Win Rate: {final['win_rate']*100:.1f}%")
        print(f"Total PnL: ${final['total_pnl']:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
