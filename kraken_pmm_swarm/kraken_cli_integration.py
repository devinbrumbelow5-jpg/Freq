#!/usr/bin/env python3
"""
Kraken CLI Integration Module
Optional integration with kraken-cli for real account verification
Does NOT interfere with existing CCXT/WebSocket trading system
"""

import os
import json
import subprocess
from pathlib import Path

# Config file for enabling/disabling
CONFIG_DIR = Path('/root/.openclaw/workspace/kraken_pmm_swarm/config')
CONFIG_FILE = CONFIG_DIR / 'kraken_cli.json'

def ensure_config():
    """Ensure config directory and file exist"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        default_config = {
            'enabled': False,
            'api_key': '',
            'api_secret': '',
            'use_for_balance_verification': False,
            'use_for_order_confirmation': False
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)

def load_config():
    """Load Kraken CLI config"""
    ensure_config()
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    """Save Kraken CLI config"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def is_enabled():
    """Check if Kraken CLI integration is enabled"""
    try:
        config = load_config()
        return config.get('enabled', False)
    except:
        return False

def enable():
    """Enable Kraken CLI integration"""
    config = load_config()
    config['enabled'] = True
    save_config(config)
    print("✅ Kraken CLI integration ENABLED")
    print("   Run 'python kraken_cli_integration.py setup' to configure API keys")

def disable():
    """Disable Kraken CLI integration"""
    config = load_config()
    config['enabled'] = False
    save_config(config)
    print("⛔ Kraken CLI integration DISABLED")
    print("   CCXT/WebSocket trading continues normally")

def get_real_balance():
    """Get real balance from Kraken CLI (if enabled)"""
    if not is_enabled():
        return None
    
    try:
        result = subprocess.run(
            ['kraken-cli', 'balance'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as e:
        return f"Error: {e}"

def status():
    """Show current Kraken CLI integration status"""
    config = load_config()
    enabled = config.get('enabled', False)
    
    print("=" * 60)
    print("KRAKEN CLI INTEGRATION STATUS")
    print("=" * 60)
    print(f"Status: {'✅ ENABLED' if enabled else '⛔ DISABLED'}")
    print(f"Config file: {CONFIG_FILE}")
    
    if enabled:
        print("\nFeatures active:")
        if config.get('use_for_balance_verification'):
            print("  ✓ Balance verification")
        if config.get('use_for_order_confirmation'):
            print("  ✓ Order confirmation")
        
        print("\nFetching real account balance...")
        balance = get_real_balance()
        if balance:
            print(f"Real balance:\n{balance}")
        else:
            print("⚠️  Could not fetch balance (API keys may not be configured)")
    else:
        print("\nCurrent trading: CCXT/WebSocket (paper trading mode)")
        print("Kraken CLI is NOT interfering with existing system")
    
    print("\nCommands:")
    print("  python kraken_cli_integration.py enable   - Enable integration")
    print("  python kraken_cli_integration.py disable  - Disable integration")
    print("  python kraken_cli_integration.py status   - Show this status")
    print("=" * 60)

def setup():
    """Interactive setup for Kraken CLI"""
    print("\n" + "=" * 60)
    print("KRAKEN CLI SETUP")
    print("=" * 60)
    print("\nThis will configure Kraken CLI for real account access.")
    print("Your existing paper trading system will NOT be affected.")
    print("\nYou need:")
    print("  1. Kraken API Key")
    print("  2. Kraken API Secret")
    print("\nCreate these at: https://www.kraken.com/u/security/api")
    print("=" * 60 + "\n")
    
    api_key = input("Enter Kraken API Key (or press Enter to skip): ").strip()
    if api_key:
        api_secret = input("Enter Kraken API Secret: ").strip()
        
        config = load_config()
        config['api_key'] = api_key
        config['api_secret'] = api_secret
        config['enabled'] = True
        save_config(config)
        
        env_file = Path.home() / '.kraken_env'
        with open(env_file, 'w') as f:
            f.write(f'export KRAKEN_API_KEY={api_key}\n')
            f.write(f'export KRAKEN_API_SECRET={api_secret}\n')
        
        print("\n✅ Configuration saved!")
        print(f"   API Key stored in: {CONFIG_FILE}")
        print(f"   Environment vars: {env_file}")
        print("\nTo use Kraken CLI, run:")
        print("   source ~/.kraken_env")
        print("   kraken-cli balance")
    else:
        print("\n⛔ Setup skipped. Run again when ready.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        status()
    elif sys.argv[1] == "enable":
        enable()
    elif sys.argv[1] == "disable":
        disable()
    elif sys.argv[1] == "status":
        status()
    elif sys.argv[1] == "setup":
        setup()
    elif sys.argv[1] == "balance":
        balance = get_real_balance()
        if balance:
            print(balance)
        else:
            print("Kraken CLI not enabled or not configured")
    else:
        print("Usage:")
        print("  python kraken_cli_integration.py enable   - Enable integration")
        print("  python kraken_cli_integration.py disable  - Disable integration")
        print("  python kraken_cli_integration.py status   - Show status")
        print("  python kraken_cli_integration.py setup    - Configure API keys")
        print("  python kraken_cli_integration.py balance  - Get real balance")
