#!/usr/bin/env python3
"""
Live Trading Dry-Run System
Simulates what orders WOULD be placed vs what Kraken CLI would execute
Shows exactly what would happen without risking real capital
"""

import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import asyncio

# Database connection
DB_PATH = Path('/root/.openclaw/workspace/kraken_pmm_swarm/coinbase_swarm.db')

class DryRunSimulator:
    """Simulates live trading without executing real orders"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.simulated_orders = []
        self.dry_run_mode = True
        
    def get_db_connection(self):
        return sqlite3.connect(self.db_path)
    
    async def get_live_paper_orders(self) -> List[Dict]:
        """Get current paper trading orders that would be placed live"""
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        orders = []
        try:
            # Get current open orders
            cursor.execute("""
                SELECT o.bot_id, o.pair, o.side, o.price, o.amount, o.status,
                       b.current_bid, b.current_ask, b.spread_bps
                FROM orders o
                JOIN bot_status b ON o.bot_id LIKE '%' || REPLACE(b.pair, '/', '') || '%'
                WHERE o.status = 'OPEN'
                ORDER BY o.created_at DESC
                LIMIT 20
            """)
            
            for row in cursor.fetchall():
                orders.append({
                    'bot_id': row['bot_id'],
                    'pair': row['pair'],
                    'side': row['side'],
                    'price': float(row['price']),
                    'amount': float(row['amount']),
                    'status': row['status'],
                    'market_bid': float(row['current_bid']) if row['current_bid'] else None,
                    'market_ask': float(row['current_ask']) if row['current_ask'] else None,
                    'spread_bps': float(row['spread_bps']) if row['spread_bps'] else None
                })
        except Exception as e:
            print(f"Error fetching orders: {e}")
        finally:
            conn.close()
        
        return orders
    
    def get_paper_position(self, bot_id: str) -> Optional[Dict]:
        """Get current paper position for a bot"""
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        position = None
        try:
            # Get fills for this bot
            cursor.execute("""
                SELECT side, SUM(amount) as total_amount, AVG(price) as avg_price
                FROM fills
                WHERE bot_id = ?
                GROUP BY side
            """, (bot_id,))
            
            buy_amount = 0.0
            sell_amount = 0.0
            buy_avg = 0.0
            
            for row in cursor.fetchall():
                if row['side'] == 'BUY':
                    buy_amount = float(row['total_amount'] or 0)
                    buy_avg = float(row['avg_price'] or 0)
                else:
                    sell_amount = float(row['total_amount'] or 0)
            
            net_position = buy_amount - sell_amount
            
            position = {
                'size': net_position,
                'avg_entry': buy_avg if net_position > 0 else 0,
                'side': 'LONG' if net_position > 0 else 'FLAT' if net_position == 0 else 'SHORT'
            }
        except Exception as e:
            print(f"Error fetching position: {e}")
        finally:
            conn.close()
        
        return position
    
    def simulate_kraken_order(self, order: Dict) -> Dict:
        """Simulate what Kraken would do with this order"""
        simulation = {
            'order': order,
            'dry_run': True,
            'timestamp': datetime.now().isoformat(),
            'actions': []
        }
        
        # Check if order is reasonable
        market_mid = (order.get('market_bid', 0) + order.get('market_ask', 0)) / 2
        if market_mid > 0:
            price_diff = abs(order['price'] - market_mid) / market_mid * 100
            
            if price_diff > 1.0:
                simulation['actions'].append(f"⚠️  WARNING: Order {price_diff:.2f}% away from market price")
                simulation['risk_level'] = 'HIGH'
            elif price_diff > 0.5:
                simulation['actions'].append(f"⚠️  CAUTION: Order {price_diff:.2f}% from market")
                simulation['risk_level'] = 'MEDIUM'
            else:
                simulation['actions'].append(f"✅ Price OK: {price_diff:.3f}% from market")
                simulation['risk_level'] = 'LOW'
        
        # Calculate what would happen
        notional = order['price'] * order['amount']
        fee = notional * 0.0026  # Taker fee
        
        simulation['actions'].append(f"Would place {order['side']} order: {order['amount']:.6f} @ ${order['price']:,.2f}")
        simulation['actions'].append(f"Notional value: ${notional:,.2f}")
        simulation['actions'].append(f"Estimated fee: ${fee:.4f}")
        simulation['actions'].append("DRY RUN: No real order placed")
        
        simulation['estimated_fee'] = fee
        simulation['notional'] = notional
        
        return simulation
    
    def run_dry_run_report(self):
        """Run dry-run simulation"""
        print("\n" + "=" * 70)
        print("LIVE TRADING DRY-RUN SIMULATION")
        print("=" * 70)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Mode:      DRY-RUN (No real orders placed)")
        print("=" * 70 + "\n")
        
        # Get current paper orders
        orders = asyncio.run(self.get_live_paper_orders())
        
        if not orders:
            print("No open orders found in paper trading system")
            print("Paper trading may not be running or no orders currently open")
            return
        
        print(f"Found {len(orders)} open orders to simulate:\n")
        
        total_notional = 0.0
        total_fees = 0.0
        
        for order in orders:
            print("-" * 70)
            print(f"ORDER: {order['bot_id']} | {order['pair']} | {order['side']}")
            print("-" * 70)
            
            # Show current paper position
            position = self.get_paper_position(order['bot_id'])
            if position and position['size'] != 0:
                print(f"Current Position: {position['side']} {position['size']:.6f} @ ${position['avg_entry']:,.2f}")
            else:
                print("Current Position: FLAT")
            
            # Simulate Kraken execution
            sim = self.simulate_kraken_order(order)
            
            for action in sim['actions']:
                print(f"  {action}")
            
            total_notional += sim.get('notional', 0)
            total_fees += sim.get('estimated_fee', 0)
            
            print()
        
        print("=" * 70)
        print("DRY-RUN SUMMARY")
        print("=" * 70)
        print(f"Total Orders:       {len(orders)}")
        print(f"Total Notional:     ${total_notional:,.2f}")
        print(f"Estimated Fees:     ${total_fees:.4f}")
        print("\n✅ This is what WOULD happen if you went live")
        print("❌ NO REAL ORDERS WERE PLACED")
        print("=" * 70 + "\n")
    
    async def continuous_monitor(self, interval=30):
        """Continuously monitor and compare paper vs simulated live"""
        print("\n" + "=" * 70)
        print("CONTINUOUS DRY-RUN MONITOR")
        print("=" * 70)
        print(f"Mode:     Dry-Run (updates every {interval}s)")
        print("Action:   Compare paper trades with simulated live execution")
        print("=" * 70 + "\n")
        
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spin_idx = 0
        
        try:
            while True:
                orders = await self.get_live_paper_orders()
                
                # Clear screen and redraw
                print(f"\033[2J\033[H", end='')
                
                print(f"{spinner[spin_idx]} DRY-RUN MONITOR | {datetime.now().strftime('%H:%M:%S')} | {len(orders)} orders")
                print("-" * 70)
                
                for order in orders[:5]:
                    pair = order['pair']
                    side = order['side']
                    price = order['price']
                    amount = order['amount']
                    notional = price * amount
                    
                    print(f"{pair:12} | {side:4} | {amount:10.6f} @ ${price:>12,.2f} | ${notional:>10,.2f}")
                
                print("-" * 70)
                print(f"Status: DRY-RUN | NO REAL ORDERS | Paper Trading Active")
                
                spin_idx = (spin_idx + 1) % len(spinner)
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nDry-run monitor stopped.")


def main():
    """Main entry point"""
    simulator = DryRunSimulator()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--monitor':
        asyncio.run(simulator.continuous_monitor())
    else:
        simulator.run_dry_run_report()
        
        print("\nTo start continuous monitoring:")
        print("  python dry_run_system.py --monitor")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
