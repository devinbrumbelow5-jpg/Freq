# Kraken PMM Swarm

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CCXT](https://img.shields.io/badge/CCXT-powered-green.svg)](https://github.com/ccxt/ccxt)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

A high-frequency passive market making trading system with autonomous risk management.

## 🚀 Quick Start

```bash
# Start the swarm
./run_swarm.sh

# View real-time dashboard
tmux attach -t swarm_dashboard

# Check bot status
./run_with_monitor.sh
```

## 📁 Project Structure

```
kraken_pmm_swarm/          # Main trading system
├── swarm_manager.py       # Orchestrator + risk management
├── pmm_bot.py            # Market making bot
├── kraken_paper_client.py # Exchange client
├── database.py           # PostgreSQL persistence
├── dashboard.py          # Real-time terminal UI
├── profit_guard.py       # Risk management
├── config_aggressive.yaml # Trading config
└── requirements.txt      # Python dependencies

HEARTBEAT.md             # System monitoring protocol
SOUL.md                  # Agent identity
AGENTS.md                # Swarm architecture docs
```

## 🎯 Trading Pairs

- BTC/USDT
- ETH/USDT
- SOL/USDT
- AVAX/USDT
- LINK/USDT
- AAVE/USDT

## ⚡ Key Features

- **WebSocket Real-Time Data**: Sub-5ms latency for market data
- **PostgreSQL Persistence**: All trades and positions logged
- **Risk Management**: Drawdown protection, position limits
- **Simulation Mode**: Realistic Kraken CLI with live order-book slippage
- **Terminal Dashboard**: Live PnL and position monitoring
- **Auto-Recovery**: Self-healing bot restart on failures

## 📊 Database Schema

PostgreSQL tables:
- `positions`: Active positions per bot
- `trades`: Complete trade history with PnL
- `balances`: Cash balance tracking
- `bot_logs`: Event logging

## 🔒 Risk Controls

- Max position size: 50% of portfolio per bot
- Inventory skew: ±0.8 limit
- Drawdown circuit breaker: 12%
- WebSocket health: < 500ms latency

## 📈 Performance

- **Current PnL**: +$177.48 realized
- **Active Positions**: 2 (ETH/USDT, BTC/USDT)
- **Uptime**: 99.9%+
- **Fill Rate**: 15-25%

## 🛠️ System Requirements

- Python 3.11+
- PostgreSQL 15+
- CCXT Pro (WebSocket support)
- Tmux (for dashboard)

## 📝 License

Private - All rights reserved.
