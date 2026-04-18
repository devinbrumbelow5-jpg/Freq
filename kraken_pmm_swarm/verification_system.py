#!/usr/bin/env python3
"""
Paper Trading Verification System
Compares CCXT paper trading results with real Kraken market data
Ensures profitability before live trading
"""

import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Database connection
DB_PATH = Path('/root/.openclaw/workspace/kraken_pmm_swarm/coinbase_swarm.db')

# ANSI colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
BOLD = '\033[1m'
RESET = '\033[0m'

# Pairs we trade
TRADING_PAIRS = ['BTC/USD', 'ETH/USD', 'SOL/USD']

class PaperTradingVerifier:
    """Verifies paper trading profitability against real market data"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.verification_results = {}
        
    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_paper_trading_stats(self) -> Dict:
        """Get paper trading statistics from database"""
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {
            'total_fills': 0,
            'total_buy_fills': 0,
            'total_sell_fills': 0,
            'gross_pnl': 0.0,
            'fees_paid': 0.0,
            'net_pnl': 0.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'avg_spread_captured': 0.0,
            'avg_fill_size': 0.0,
            'fills_by_pair': {},
            'recent_trades': []
        }
        
        try:
            # Get all fills
            cursor.execute("""
                SELECT pair, side, price, amount, filled_at, fee
                FROM fills
                ORDER BY filled_at DESC
            """)
            
            fills = cursor.fetchall()
            stats['total_fills'] = len(fills)
            
            total_volume = 0.0
            spreads = []
            
            for fill in fills:
                pair = fill['pair']
                side = fill['side']
                price = float(fill['price'])
                amount = float(fill['amount'])
                fee = float(fill['fee']) if fill['fee'] else 0.0
                
                if side == 'BUY':
                    stats['total_buy_fills'] += 1
                else:
                    stats['total_sell_fills'] += 1
                
                # Calculate spread captured (simplified - actual would need bid/ask)
                spread = amount * price * 0.002  # Approximate 20 bps
                spreads.append(spread)
                
                stats['fees_paid'] += fee
                total_volume += amount
                
                if pair not in stats['fills_by_pair']:
                    stats['fills_by_pair'][pair] = {'count': 0, 'volume': 0.0}
                stats['fills_by_pair'][pair]['count'] += 1
                stats['fills_by_pair'][pair]['volume'] += amount
            
            if spreads:
                stats['avg_spread_captured'] = sum(spreads) / len(spreads)
            if stats['total_fills'] > 0:
                stats['avg_fill_size'] = total_volume / stats['total_fills']
            
            # Get PnL from pnl table (this is where it's actually stored)
            cursor.execute("""
                SELECT 
                    SUM(realized_pnl) as total_realized,
                    SUM(unrealized_pnl) as total_unrealized,
                    SUM(fees_paid) as total_fees
                FROM pnl
            """)
            
            row = cursor.fetchone()
            if row and row['total_realized'] is not None:
                stats['realized_pnl'] = float(row['total_realized'] or 0)
                stats['unrealized_pnl'] = float(row['total_unrealized'] or 0)
                stats['fees_paid'] = float(row['total_fees'] or 0)
                # NET PnL = Gross - Fees
                stats['net_pnl'] = stats['realized_pnl'] - stats['fees_paid'] + stats['unrealized_pnl']
                stats['fees_paid'] = float(row['total_fees'] or 0)
            
            # Get PnL by pair
            cursor.execute("""
                SELECT pair, 
                       SUM(realized_pnl) as realized,
                       SUM(fees_paid) as fees
                FROM pnl
                GROUP BY pair
            """)
            
            stats['pnl_by_pair'] = {}
            for row in cursor.fetchall():
                stats['pnl_by_pair'][row['pair']] = {
                    'realized': float(row['realized'] or 0),
                    'fees': float(row['fees'] or 0)
                }
            
            # Get recent trades for verification
            cursor.execute("""
                SELECT pair, side, price, amount, filled_at
                FROM fills
                ORDER BY filled_at DESC
                LIMIT 20
            """)
            
            stats['recent_trades'] = [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            conn.close()
        
        return stats
    
    def get_kraken_market_prices(self) -> Dict[str, float]:
        """Get current market prices from Kraken CLI"""
        prices = {}
        
        try:
            # Check if kraken-cli is available
            result = subprocess.run(
                ['which', 'kraken-cli'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print("⚠️  Kraken CLI not found in PATH")
                return prices
            
            # Try to get ticker info
            result = subprocess.run(
                ['kraken-cli', 'ticker', '--raw'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                try:
                    ticker_data = json.loads(result.stdout)
                    # Map exchange pairs to our format
                    pair_map = {
                        'XXBTZUSD': 'BTC/USD',
                        'XETHZUSD': 'ETH/USD',
                        'SOLUSD': 'SOL/USD'
                    }
                    
                    for kraken_pair, data in ticker_data.items():
                        if kraken_pair in pair_map:
                            our_pair = pair_map[kraken_pair]
                            prices[our_pair] = {
                                'bid': float(data.get('bid', 0)),
                                'ask': float(data.get('ask', 0)),
                                'last': float(data.get('last', 0))
                            }
                except json.JSONDecodeError:
                    print("⚠️  Could not parse Kraken ticker data")
            else:
                print("⚠️  Kraken CLI not configured (run: python kraken_cli_integration.py setup)")
                
        except subprocess.TimeoutExpired:
            print("⚠️  Kraken CLI timeout")
        except Exception as e:
            print(f"⚠️  Kraken CLI error: {e}")
        
        return prices
    
    def verify_trade_prices(self, paper_stats: Dict, market_prices: Dict) -> Dict:
        """Verify paper trading prices match real market"""
        verification = {
            'price_accuracy': {},
            'discrepancies': [],
            'overall_accuracy': 0.0
        }
        
        if not market_prices:
            verification['status'] = 'NO_MARKET_DATA'
            return verification
        
        total_accuracy = 0.0
        count = 0
        
        for trade in paper_stats.get('recent_trades', [])[:10]:
            pair = trade['pair']
            paper_price = float(trade['price'])
            
            if pair in market_prices:
                market_bid = market_prices[pair]['bid']
                market_ask = market_prices[pair]['ask']
                market_mid = (market_bid + market_ask) / 2
                
                # Calculate price difference
                price_diff_pct = abs(paper_price - market_mid) / market_mid * 100
                
                verification['price_accuracy'][pair] = {
                    'paper_price': paper_price,
                    'market_mid': market_mid,
                    'difference_bps': price_diff_pct * 100,  # Convert to basis points
                    'accurate': price_diff_pct < 0.05  # Within 5 bps is good
                }
                
                if price_diff_pct >= 0.05:
                    verification['discrepancies'].append({
                        'pair': pair,
                        'paper': paper_price,
                        'market': market_mid,
                        'diff_pct': price_diff_pct
                    })
                
                total_accuracy += (1.0 - min(price_diff_pct, 1.0))
                count += 1
        
        if count > 0:
            verification['overall_accuracy'] = (total_accuracy / count) * 100
        
        verification['status'] = 'VERIFIED' if verification['overall_accuracy'] > 95 else 'NEEDS_REVIEW'
        
        return verification
    
    def calculate_profitability_score(self, stats: Dict) -> Tuple[float, str]:
        """Calculate overall profitability score"""
        score = 0.0
        factors = []
        
        # Net PnL factor (40%)
        if stats['net_pnl'] > 0:
            pnl_score = min(40, 40 * (stats['net_pnl'] / 100))  # $100 = max score
            score += pnl_score
            factors.append(f"Net PnL (${stats['net_pnl']:.2f}): +{pnl_score:.1f}")
        else:
            factors.append(f"Net PnL (${stats['net_pnl']:.2f}): 0.0")
        
        # Fill rate factor (20%)
        if stats['total_fills'] > 50:
            fill_score = min(20, stats['total_fills'] / 10)
            score += fill_score
            factors.append(f"Fill count ({stats['total_fills']}): +{fill_score:.1f}")
        
        # Spread capture factor (20%)
        if stats['avg_spread_captured'] > 0.1:
            spread_score = min(20, stats['avg_spread_captured'] * 100)
            score += spread_score
            factors.append(f"Spread capture: +{spread_score:.1f}")
        
        # Buy/Sell balance (20%)
        if stats['total_buy_fills'] > 0 and stats['total_sell_fills'] > 0:
            balance = min(stats['total_buy_fills'], stats['total_sell_fills']) / max(stats['total_buy_fills'], stats['total_sell_fills'])
            balance_score = 20 * balance
            score += balance_score
            factors.append(f"Balance ratio: +{balance_score:.1f}")
        
        rating = 'EXCELLENT' if score >= 80 else 'GOOD' if score >= 60 else 'FAIR' if score >= 40 else 'POOR'
        
        return score, rating, factors
    
    def run_verification(self):
        """Run full verification report"""
        print("\n" + "=" * 70)
        print("PAPER TRADING VERIFICATION REPORT")
        print("=" * 70)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")
        
        # Get paper trading stats
        print("📊 FETCHING PAPER TRADING DATA...")
        stats = self.get_paper_trading_stats()
        
        # Get real market prices
        print("📡 FETCHING KRAKEN MARKET DATA...")
        market_prices = self.get_kraken_market_prices()
        
        # Verify prices
        print("🔍 VERIFYING PRICE ACCURACY...\n")
        verification = self.verify_trade_prices(stats, market_prices)
        
        # Display results
        print("-" * 70)
        print("PAPER TRADING PERFORMANCE")
        print("-" * 70)
        print(f"Total Fills:        {stats['total_fills']}")
        print(f"  Buy Fills:        {stats['total_buy_fills']}")
        print(f"  Sell Fills:       {stats['total_sell_fills']}")
        print(f"Gross Realized PnL: ${stats['realized_pnl']:.4f}")
        print(f"Fees Paid:          ${stats['fees_paid']:.4f}")
        print(f"{BOLD}Net Realized PnL:   ${stats['net_pnl']:.4f}{RESET}")
        print(f"Unrealized PnL:     ${stats['unrealized_pnl']:.4f}")
        print(f"Avg Spread:         ${stats['avg_spread_captured']:.4f}")
        print(f"Avg Fill Size:      {stats['avg_fill_size']:.6f}")
        
        print("\n" + "-" * 70)
        print("PnL BY PAIR (Net of Fees)")
        print("-" * 70)
        for pair, data in stats.get('pnl_by_pair', {}).items():
            net = data['realized'] - data['fees']
            print(f"{pair:12} | Gross: ${data['realized']:>10.4f} | Fees: ${data['fees']:>10.4f} | Net: ${net:>10.4f}")
        
        print("\n" + "-" * 70)
        print("FILLS BY PAIR")
        print("-" * 70)
        for pair, data in stats['fills_by_pair'].items():
            print(f"{pair}: {data['count']} fills, {data['volume']:.6f} volume")
        
        if market_prices:
            print("\n" + "-" * 70)
            print("REAL MARKET PRICES (Kraken)")
            print("-" * 70)
            for pair, prices in market_prices.items():
                print(f"{pair}: Bid ${prices['bid']:,.2f} | Ask ${prices['ask']:,.2f} | Last ${prices['last']:,.2f}")
            
            print("\n" + "-" * 70)
            print("PRICE VERIFICATION")
            print("-" * 70)
            print(f"Overall Accuracy:   {verification['overall_accuracy']:.1f}%")
            print(f"Status:             {verification['status']}")
            
            if verification['discrepancies']:
                print("\n⚠️  DISCREPANCIES FOUND:")
                for disc in verification['discrepancies']:
                    print(f"   {disc['pair']}: {disc['diff_pct']:.3f}% difference")
        else:
            print("\n⚠️  Kraken CLI not available - price verification skipped")
            print("   To enable: python kraken_cli_integration.py setup")
        
        # Profitability score
        print("\n" + "-" * 70)
        print("PROFITABILITY ASSESSMENT")
        print("-" * 70)
        score, rating, factors = self.calculate_profitability_score(stats)
        
        for factor in factors:
            print(f"  {factor}")
        
        print(f"\n  TOTAL SCORE: {score:.1f}/100")
        
        rating_color = {
            'EXCELLENT': '\033[92m',  # Green
            'GOOD': '\033[96m',       # Cyan
            'FAIR': '\033[93m',       # Yellow
            'POOR': '\033[91m'        # Red
        }.get(rating, '')
        
        print(f"  RATING: {rating_color}{rating}\033[0m")
        
        # Recommendations
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        
        if rating == 'EXCELLENT':
            print("✅ System is performing excellently!")
            print("✅ Ready for live trading consideration")
            print("✅ Continue current strategy")
        elif rating == 'GOOD':
            print("✅ System is profitable")
            print("⚠️  Consider running longer before live trading")
            print("ℹ️  Monitor for consistency over next 24-48 hours")
        elif rating == 'FAIR':
            print("⚠️  System shows promise but needs improvement")
            print("ℹ️  Review spread settings and fill rates")
            print("❌ Not yet ready for live trading")
        else:
            print("❌ System is not profitable")
            print("ℹ️  Review strategy parameters")
            print("❌ DO NOT proceed to live trading")
        
        # Save report
        report_file = Path('/root/.openclaw/workspace/kraken_pmm_swarm/verification_reports')
        report_file.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = report_file / f'verification_{timestamp}.json'
        
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'paper_stats': stats,
                'market_prices': market_prices,
                'verification': verification,
                'score': score,
                'rating': rating
            }, f, indent=2, default=str)
        
        print(f"\n📁 Report saved: {report_path}")
        print("=" * 70 + "\n")
        
        return rating in ['EXCELLENT', 'GOOD']


def main():
    """Main entry point"""
    verifier = PaperTradingVerifier()
    ready_for_live = verifier.run_verification()
    
    return 0 if ready_for_live else 1


if __name__ == "__main__":
    sys.exit(main())
