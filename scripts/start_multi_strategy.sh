#!/bin/bash
# Start multi-strategy trading swarm

echo "🚀 Starting Multi-Strategy Trading Swarm v2.0"
echo "=============================================="

# Clean up old processes
echo "Cleaning up old processes..."
pkill -9 -f drawdown_regime_guard.py 2>/dev/null
pkill -9 -f freqtrade_range 2>/dev/null
sleep 2

# Check if containers are running
echo "Checking Docker containers..."
docker ps --format "table {{.Names}}" | grep -q freqtrade-range || {
    echo "Starting freqtrade-range container..."
    cd /root/.openclaw/workspace/freqtrade
    docker compose up -d freqtrade-range
    sleep 10
}

# Start additional strategy containers
echo "Starting strategy containers..."
cd /root/.openclaw/workspace/freqtrade

# Grid Scalper
docker run -d --name freqtrade-grid \
    --restart unless-stopped \
    -v /root/.openclaw/workspace/freqtrade/user_data:/freqtrade/user_data:cached \
    -v /root/.openclaw/workspace/memory:/freqtrade/memory:cached \
    -p 8083:8080 \
    freqtradeorg/freqtrade:stable_freqai \
    trade --config /freqtrade/user_data/config_multi_strategy.json \
    --strategy GridScalper_v1 \
    --db-url sqlite:////freqtrade/user_data/trades_grid.sqlite 2>/dev/null || echo "Grid container already running or failed"

# Breakout Momentum
docker run -d --name freqtrade-breakout \
    --restart unless-stopped \
    -v /root/.openclaw/workspace/freqtrade/user_data:/freqtrade/user_data:cached \
    -v /root/.openclaw/workspace/memory:/freqtrade/memory:cached \
    -p 8084:8080 \
    freqtradeorg/freqtrade:stable_freqai \
    trade --config /freqtrade/user_data/config_multi_strategy.json \
    --strategy BreakoutMomentum_v1 \
    --db-url sqlite:////freqtrade/user_data/trades_breakout.sqlite 2>/dev/null || echo "Breakout container already running or failed"

# Start regime guard with flock (prevents duplicates)
echo "Starting regime guard..."
flock -n /tmp/regime_guard.lock -c 'python3 /root/.openclaw/workspace/scripts/drawdown_regime_guard.py' >> /root/.openclaw/workspace/logs/regime_guard_cron.log 2>&1 &

# Start orchestrator
echo "Starting strategy orchestrator..."
cd /root/.openclaw/workspace
python3 scripts/multi_strategy_orchestrator.py >> logs/orchestrator.log 2>&1 &

echo ""
echo "✅ Multi-Strategy Swarm Started!"
echo "================================"
echo "Active containers:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep freqtrade
echo ""
echo "API Endpoints:"
echo "  - Range Strategy:     http://localhost:8082"
echo "  - Grid Strategy:      http://localhost:8083"
echo "  - Breakout Strategy:  http://localhost:8084"
echo ""
echo "Monitor with:"
echo "  tail -f /root/.openclaw/workspace/logs/orchestrator.log"