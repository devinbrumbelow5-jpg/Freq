# Kraken PMM Swarm

A high-frequency passive market making trading system running on Kraken exchange with 6 trading pairs (BTC, ETH, SOL, AVAX, LINK, AAVE).

## Architecture

- **Swarm Manager**: Orchestrates multiple PMM bots with centralized risk management
- **PMM Bots**: Individual market makers per trading pair
- **WebSocket Feeds**: Real-time price and order book data
- **PostgreSQL**: Trade and position persistence
- **Dashboard**: Real-time terminal-based monitoring
- **Simulation Mode**: Realistic Kraken CLI with live order-book slippage

## Quick Start

```bash
# Start the swarm
./run_swarm.sh

# View dashboard
tmux attach -t swarm_dashboard

# Check status
./run_with_monitor.sh
```

## Configuration

- `config_aggressive.yaml`: Main trading configuration
- `kraken-pmm-swarm.service`: Systemd service file

## Components

| File | Purpose |
|------|---------|
| `swarm_manager.py` | Main orchestrator with risk management |
| `pmm_bot.py` | Individual market maker bot |
| `kraken_paper_client.py` | Kraken exchange client with paper trading |
| `database.py` | PostgreSQL persistence layer |
| `dashboard.py` | Real-time terminal dashboard |
| `profit_guard.py` | Risk management and drawdown protection |
| `verification_system.py` | System verification and health checks |
| `live_readiness.py` | Live trading readiness checker |
| `dry_run_system.py` | Dry run simulation |

## Trading Pairs

- BTC/USDT
- ETH/USDT
- SOL/USDT
- AVAX/USDT
- LINK/USDT
- AAVE/USDT

## Risk Controls

- Max position size limits per bot
- Inventory skew management
- Drawdown circuit breakers
- WebSocket health monitoring
- PostgreSQL data synchronization

## Requirements

See `requirements.txt` for Python dependencies.

## Database

PostgreSQL with tables:
- `positions`: Current positions per bot
- `trades`: Trade history and PnL
- `balances`: Cash balances
- `bot_logs`: Event logs

## Monitoring

- Real-time dashboard (2-second updates)
- Tmux session: `swarm_dashboard`
- WebSocket latency monitoring
- PnL tracking (realized + unrealized)
