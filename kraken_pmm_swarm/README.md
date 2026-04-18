# Kraken PMM Swarm

CCXT-based Perpetual Market Making System with paper trading.

## Features
- 6 independent PMM bots (BTC, ETH, SOL, DOT, LINK, ADA)
- Real-time Kraken WebSocket order book data
- 100% paper trading simulation
- Dynamic spread based on order book imbalance
- Inventory skew for market neutrality
- SQLite persistence for orders/fills/P&L
- Rich terminal dashboard

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the swarm
python main.py
```

## Configuration
Edit `config.yaml` to adjust:
- Paper trading balances
- Base spreads per pair
- Order amounts
- Position limits

## Architecture
- `kraken_paper_client.py` - CCXT Pro WebSocket + paper trading
- `pmm_bot.py` - Individual bot logic with dynamic spread
- `swarm_manager.py` - Orchestration + dashboard
- `database.py` - SQLite persistence

## Dashboard
Live display shows:
- Bot status, bids/asks, spreads
- Positions and inventory skew
- Recent fills
- Paper balances
- P&L summary

Press Ctrl+C to stop gracefully.
