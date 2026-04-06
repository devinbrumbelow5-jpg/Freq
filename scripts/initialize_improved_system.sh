#!/bin/bash
# Initialize Improved Multi-Strategy Trading System

echo "🚀 Initializing Kimmy Scalper v2.0 - IMPROVED"
echo "=============================================="

# Check dependencies
echo "[1/8] Checking dependencies..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found"; exit 1; }
command -v sqlite3 >/dev/null 2>&1 || { echo "❌ sqlite3 not found"; exit 1; }

# Create necessary directories
echo "[2/8] Creating directory structure..."
mkdir -p /root/.openclaw/workspace/{memory,logs,backups,data}
mkdir -p /root/.openclaw/workspace/freqtrade/user_data/{strategies,data/okx}

# Set permissions
echo "[3/8] Setting permissions..."
chmod +x /root/.openclaw/workspace/scripts/*.sh
chmod +x /root/.openclaw/workspace/scripts/*.py

# Create databases
echo "[4/8] Creating trade databases..."
sqlite3 /root/.openclaw/workspace/freqtrade/user_data/trades_grid.sqlite "CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, pair TEXT, is_open BOOLEAN, open_date TEXT, close_date TEXT, close_profit REAL, strategy TEXT);" 2>/dev/null || true
sqlite3 /root/.openclaw/workspace/freqtrade/user_data/trades_breakout.sqlite "CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, pair TEXT, is_open BOOLEAN, open_date TEXT, close_date TEXT, close_profit REAL, strategy TEXT);" 2>/dev/null || true

# Update crontab with new orchestrator
echo "[5/8] Updating crontab..."
cat > /root/.openclaw/workspace/config/improved_crontab << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Multi-Strategy Orchestrator - Every 5 minutes
*/5 * * * * cd /root/.openclaw/workspace && flock -n /tmp/orchestrator.lock -c 'python3 scripts/multi_strategy_orchestrator.py --rotate' >> logs/orchestrator.log 2>&1

# Smart Position Sizing Check - Every hour
0 * * * * cd /root/.openclaw/workspace && python3 scripts/smart_position_sizing.py >> logs/position_sizing.log 2>&1

# Portfolio Heat Check - Every minute
* * * * * cd /root/.openclaw/workspace && flock -n /tmp/regime_guard.lock -c 'python3 scripts/drawdown_regime_guard.py' >> logs/regime_guard_cron.log 2>&1

# Health Monitor - Every 5 minutes
*/5 * * * * cd /root/.openclaw/workspace && ./scripts/health_check.sh >> logs/health_check.log 2>&1

# Log rotation - Daily at 2 AM
0 2 * * * cd /root/.openclaw/workspace/logs && find . -name "*.log" -size +50M -exec > {} \;

# Database backup - Daily at 4 AM
0 4 * * * cd /root/.openclaw/workspace && cp freqtrade/user_data/trades_*.sqlite backups/ 2>/dev/null
EOF

crontab /root/.openclaw/workspace/config/improved_crontab

# Start web dashboard
echo "[6/8] Starting web dashboard..."
cd /root/.openclaw/workspace/ui
python3 -m http.server 3000 >> /root/.openclaw/workspace/logs/dashboard.log 2>&1 &
echo "Dashboard available at: http://localhost:3000/dashboard.html"

# Start multi-strategy swarm
echo "[7/8] Starting multi-strategy swarm..."
cd /root/.openclaw/workspace
./scripts/start_multi_strategy.sh

# Initialize smart position sizing
echo "[8/8] Initializing smart position sizing..."
python3 scripts/smart_position_sizing.py >> logs/position_sizing.log 2>&1

echo ""
echo "✅ IMPROVED SYSTEM INITIALIZED!"
echo "================================"
echo ""
echo "New Features Deployed:"
echo "  ✓ Grid Scalper Strategy"
echo "  ✓ Breakout Momentum Strategy"
echo "  ✓ Multi-Strategy Orchestrator"
echo "  ✓ Smart Position Sizing (Kelly Criterion)"
echo "  ✓ Web Dashboard (http://localhost:3000)"
echo "  ✓ Portfolio Heat Management"
echo "  ✓ Correlation Risk Protection"
echo "  ✓ Improved Cron Scheduling"
echo ""
echo "Active Strategies:"
echo "  - Mean Reversion: 35% allocation"
echo "  - Grid Scalper: 40% allocation"
echo "  - Breakout Momentum: 25% allocation"
echo ""
echo "Monitoring:"
echo "  - Dashboard: http://localhost:3000/dashboard.html"
echo "  - API Range: http://localhost:8082"
echo "  - API Grid: http://localhost:8083"
echo "  - API Breakout: http://localhost:8084"
echo ""
echo "Commands:"
echo "  tail -f logs/orchestrator.log - View orchestrator"
echo "  tail -f logs/position_sizing.log - View sizing calculations"
echo "  docker ps - View running containers"