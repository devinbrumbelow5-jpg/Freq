# SKILL.md - freqtrade_trade

## Description
Start/stop Freqtrade trading bots with safety-first defaults. Always uses --dry-run mode unless explicitly overridden.

## Usage
```bash
python3 skills/freqtrade_trade/freqtrade_trade.py [OPTIONS]
```

## Options
- `--strategy` - Strategy name (default: AetherFreqaiStrategy)
- `--pairs` - Comma-separated pairs (default: BTC/USDC,ETH/USDC,SOL/USDC)
- `--dry-run` - Dry run mode (default: True)
- `--live` - WARNING: Enable live trading (requires confirmation)
- `--action` - Action: start/stop/restart (default: start)
- `--port` - Web UI port (default: 8080)
- `--gpu` - Enable GPU acceleration

## Examples
```bash
# Start paper trading bot
python3 skills/freqtrade_trade/freqtrade_trade.py --strategy AetherFreqaiStrategy

# Start with specific pairs
python3 skills/freqtrade_trade/freqtrade_trade.py --pairs BTC/USDC,ETH/USDC

# Enable live trading (requires confirmation)
python3 skills/freqtrade_trade/freqtrade_trade.py --live --strategy AetherFreqaiStrategy

# Stop all bots
python3 skills/freqtrade_trade/freqtrade_trade.py --action stop
```

## Safety
- Dry-run is default and mandatory
- Live trading requires explicit `--live` flag
- Confirmation prompt for live mode
- Container health monitoring

## Output
- Container ID
- Status confirmation
- Web UI URL
- Mode confirmation (dry-run/live)
