#!/usr/bin/env python3
"""
Live Trading Readiness System
One-stop shop for verifying paper trading and preparing for live trading
"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, '/root/.openclaw/workspace/kraken_pmm_swarm')

from verification_system import PaperTradingVerifier
from dry_run_system import DryRunSimulator

def show_menu():
    """Show main menu"""
    print("\n" + "=" * 70)
    print("LIVE TRADING READINESS SYSTEM")
    print("=" * 70)
    print("\n📊 VERIFICATION COMMANDS:")
    print("  1. Run profitability verification")
    print("  2. Run dry-run simulation")
    print("  3. Start continuous dry-run monitor")
    print("  4. Check Kraken CLI setup")
    print("  5. Compare paper vs real prices")
    print("\n🚀 GO LIVE COMMANDS:")
    print("  6. Live trading checklist")
    print("  7. Enable Kraken CLI integration")
    print("\n  0. Exit")
    print("=" * 70)

def run_verification():
    """Run profitability verification"""
    verifier = PaperTradingVerifier()
    ready = verifier.run_verification()
    
    if ready:
        print("\n✅ System is profitable and ready for consideration")
    else:
        print("\n⚠️  System needs improvement before live trading")
    
    return ready

def run_dry_run():
    """Run dry-run simulation"""
    simulator = DryRunSimulator()
    simulator.run_dry_run_report()

def run_monitor():
    """Start continuous monitor"""
    import asyncio
    simulator = DryRunSimulator()
    asyncio.run(simulator.continuous_monitor())

def check_kraken_cli():
    """Check Kraken CLI setup"""
    print("\n" + "=" * 70)
    print("KRAKEN CLI STATUS CHECK")
    print("=" * 70)
    
    # Check if kraken-cli exists
    result = subprocess.run(['which', 'kraken-cli'], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Kraken CLI binary found")
    else:
        print("❌ Kraken CLI not found")
        print("   Install with: npm install -g kraken-cli")
        return
    
    # Check config
    config_file = Path('/root/.openclaw/workspace/kraken_pmm_swarm/config/kraken_cli.json')
    if config_file.exists():
        import json
        with open(config_file) as f:
            config = json.load(f)
        
        print(f"✅ Config file exists: {config_file}")
        print(f"   Enabled: {config.get('enabled', False)}")
        print(f"   API Key configured: {'Yes' if config.get('api_key') else 'No'}")
        
        if config.get('enabled') and config.get('api_key'):
            print("\n🔍 Testing API connection...")
            result = subprocess.run(
                ['kraken-cli', 'balance'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print("✅ API connection successful!")
                print("\nReal account balances:")
                print(result.stdout)
            else:
                print("❌ API connection failed")
                print(f"   Error: {result.stderr}")
    else:
        print(f"❌ Config not found: {config_file}")
        print("   Run: python kraken_cli_integration.py setup")

def compare_prices():
    """Compare paper trading prices with real market"""
    print("\n" + "=" * 70)
    print("PRICE COMPARISON")
    print("=" * 70)
    
    # Get paper trading prices from DB
    import sqlite3
    from datetime import datetime
    
    db = sqlite3.connect('/root/.openclaw/workspace/kraken_pmm_swarm/coinbase_swarm.db')
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT pair, price, filled_at
        FROM fills
        ORDER BY filled_at DESC
        LIMIT 5
    """)
    
    print("\nRecent Paper Trading Fills:")
    print("-" * 70)
    for row in cursor.fetchall():
        print(f"{row[0]:15} | ${row[1]:>15,.2f} | {row[2]}")
    
    db.close()
    
    # Try to get real Kraken prices
    print("\nFetching real Kraken prices...")
    result = subprocess.run(
        ['kraken-cli', 'ticker', '--raw'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        import json
        try:
            prices = json.loads(result.stdout)
            print("\nReal Kraken Market Prices:")
            print("-" * 70)
            for pair, data in prices.items():
                print(f"{pair}: Bid ${data.get('bid', 0):,.2f} | Ask ${data.get('ask', 0):,.2f}")
        except:
            print("Could not parse price data")
    else:
        print("❌ Kraken CLI not configured")
        print("   Run: python kraken_cli_integration.py setup")

def live_checklist():
    """Show live trading checklist"""
    print("\n" + "=" * 70)
    print("LIVE TRADING CHECKLIST")
    print("=" * 70)
    
    checks = [
        ("Paper trading profitable for 7+ days", False),
        ("Profit factor > 1.5", False),
        ("Max drawdown < 5%", False),
        ("Kraken CLI configured with API keys", False),
        ("Balance verification working", False),
        ("Dry-run simulation completed", False),
        ("Emergency stop procedures tested", False),
        ("Risk limits configured", False),
    ]
    
    for check, status in checks:
        symbol = "✅" if status else "❌"
        print(f"{symbol} {check}")
    
    print("\n" + "=" * 70)
    print("⚠️  ALL items must be ✅ before going live")
    print("=" * 70)

def enable_live():
    """Enable live trading (requires confirmation)"""
    print("\n" + "=" * 70)
    print("ENABLE LIVE TRADING")
    print("=" * 70)
    print("\n⚠️  WARNING: This will configure the system for REAL trading")
    print("   Real money will be at risk!")
    print("\nRequirements:")
    print("  1. Paper trading profitable for minimum 7 days")
    print("  2. Kraken API keys configured")
    print("  3. Risk limits set and tested")
    print("  4. You understand the risks")
    
    confirm = input("\nType 'GO LIVE' to proceed (anything else to cancel): ")
    
    if confirm == "GO LIVE":
        print("\n🚀 Configuring for live trading...")
        print("   This will:")
        print("   - Enable Kraken CLI integration")
        print("   - Switch from paper to real trading")
        print("   - Activate risk monitoring")
        
        # Run setup
        subprocess.run([sys.executable, 'kraken_cli_integration.py', 'enable'])
        
        print("\n✅ Live trading configuration complete")
        print("   Review settings in: config/kraken_cli.json")
    else:
        print("\n❌ Live trading setup cancelled")

def main():
    """Main menu loop"""
    while True:
        show_menu()
        
        try:
            choice = input("\nEnter command (0-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        
        if choice == '0':
            print("\nGoodbye!")
            break
        elif choice == '1':
            run_verification()
        elif choice == '2':
            run_dry_run()
        elif choice == '3':
            print("\nStarting continuous monitor (Ctrl+C to stop)...")
            run_monitor()
        elif choice == '4':
            check_kraken_cli()
        elif choice == '5':
            compare_prices()
        elif choice == '6':
            live_checklist()
        elif choice == '7':
            enable_live()
        else:
            print("\nInvalid choice. Please enter 0-7.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
