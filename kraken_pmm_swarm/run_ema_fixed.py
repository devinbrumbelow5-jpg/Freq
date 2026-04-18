#!/usr/bin/env python3
"""EMA Crossover - Fixed Position Sizing for Profitable Trading"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ema_bot import EMACrossoverBot, EMAConfig
from coinbase_paper_client import CoinbasePaperClient
from database import DatabaseManager

async def main():
    print("=" * 70)
    print("EMA CROSSOVER STRATEGY - FIXED VERSION")
    print("Backtested: 491% return, 1.30 Sharpe (3 years BTC)")
    print("Fast EMA: 12 | Slow EMA: 26")
    print("=" * 70)
    
    # FIXED: Proper position sizing
    # $10,000 total / 3 pairs = ~$3,333 per pair max
    # Use 30% of per-pair allocation per trade = ~$1,000 per trade
    # This allows multiple entry/exit cycles without balance exhaustion
    TOTAL_CAPITAL = 10000
    NUM_PAIRS = 3
    CAPITAL_PER_PAIR = TOTAL_CAPITAL / NUM_PAIRS  # ~$3,333
    POSITION_SIZE = CAPITAL_PER_PAIR * 0.30  # ~$1,000 per position
    
    client = CoinbasePaperClient(
        paper_balances={'USD': TOTAL_CAPITAL, 'BTC': 0.05, 'ETH': 0.3, 'SOL': 3.0},
        max_slippage_pct=0.02
    )
    
    db = DatabaseManager('./ema_fixed.db')
    await db.connect()
    
    # Create 3 bots for BTC, ETH, SOL - FIXED position sizes
    bots = []
    configs = [
        ('ema_btc', 'BTC/USD', POSITION_SIZE),
        ('ema_eth', 'ETH/USD', POSITION_SIZE),
        ('ema_sol', 'SOL/USD', POSITION_SIZE)
    ]
    
    print(f"\n💰 Capital Allocation:")
    print(f"   Total: ${TOTAL_CAPITAL:,.2f}")
    print(f"   Per Pair: ${CAPITAL_PER_PAIR:,.2f}")
    print(f"   Position Size: ${POSITION_SIZE:,.2f}")
    print(f"   Strategy: 30% of pair allocation per trade")
    print()
    
    for bot_id, pair, size in configs:
        bot = EMACrossoverBot(
            bot_id=bot_id,
            config=EMAConfig(
                pair=pair,
                fast_period=12,
                slow_period=26,
                order_size_usd=size,
                stop_loss_pct=3.0  # Tighter stops for better R/R
            ),
            client=client,
            database=db
        )
        bots.append((bot_id, bot))
    
    await client.start(['BTC/USD', 'ETH/USD', 'SOL/USD'])
    await asyncio.sleep(3)
    
    for bot_id, bot in bots:
        await bot.start()
        print(f"✓ Started {bot_id} (${POSITION_SIZE:,.0f} positions)")
    
    print("\n" + "=" * 70)
    print("All 3 EMA strategies ACTIVE")
    print("Collecting price data (need 26 periods for EMA calculation)...")
    print("=" * 70 + "\n")
    
    last_status = ""
    status_counter = 0
    
    try:
        while True:
            await asyncio.sleep(10)  # Update every 10 seconds
            
            # Build status line
            total_trades = sum(bot.get_stats()['trades'] for _, bot in bots)
            
            # Only print detailed status every 6 iterations (60 seconds) or if trades changed
            status_counter += 1
            current_status = f"Trades: {total_trades}"
            
            if status_counter >= 6 or current_status != last_status:
                status_counter = 0
                last_status = current_status
                
                now = datetime.now().strftime('%H:%M:%S')
                print(f"\n[{now}] Status Update")
                print(f"{'Bot':<12} {'Pair':<10} {'Trades':<8} {'Win%':<8} {'PnL%':<10} {'Position':<12}")
                print("-" * 70)
                
                total_pnl = 0
                for bot_id, bot in bots:
                    stats = bot.get_stats()
                    pos = client.get_position(stats['pair'])
                    total_pnl += stats['total_pnl_pct']
                    print(f"{bot_id:<12} {stats['pair']:<10} {stats['trades']:<8} "
                          f"{stats['win_rate']*100:>6.1f}%   {stats['total_pnl_pct']:>+7.2f}%   "
                          f"{pos:>10.6f}")
                
                # Show balances
                balances = client.get_all_balances()
                usd_bal = balances.get('USD', {}).get('available', 0)
                btc_bal = balances.get('BTC', {}).get('available', 0)
                eth_bal = balances.get('ETH', {}).get('available', 0)
                sol_bal = balances.get('SOL', {}).get('available', 0)
                
                print(f"\nBalances: USD=${usd_bal:,.2f} | BTC={btc_bal:.6f} | "
                      f"ETH={eth_bal:.4f} | SOL={sol_bal:.3f}")
                print(f"Combined PnL: {total_pnl:+.2f}% | Total Trades: {total_trades}")
                print("=" * 70)
                      
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("SHUTTING DOWN...")
        print("=" * 70)
        
        for _, bot in bots:
            await bot.stop()
        await client.stop()
        await db.close()
        
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)
        
        total_trades = 0
        total_pnl = 0
        for bot_id, bot in bots:
            final = bot.get_stats()
            total_trades += final['trades']
            total_pnl += final['total_pnl_pct']
            print(f"{bot_id:<12}: {final['trades']} trades, {final['win_rate']*100:>5.1f}% WR, "
                  f"{final['total_pnl_pct']:>+7.2f}%")
        
        print("-" * 70)
        print(f"{'TOTAL':<12}: {total_trades} trades, {total_pnl:>+7.2f}% combined")
        print("=" * 70)

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
