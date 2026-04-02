#!/bin/bash
# Freq Complete System Startup
# Run this after reboot or to restart all monitoring

echo "=== FREQ SYSTEM STARTUP ==="
echo "Timestamp: $(date)"

# Create necessary directories
mkdir -p /root/.openclaw/workspace/logs
mkdir -p /root/.openclaw/workspace/freqtrade/user_data/logs

# Clean stale PID files
echo "Cleaning stale PID files..."
rm -f /root/.openclaw/workspace/*.pid
rm -f /root/.openclaw/workspace/profits/*.pid
rm -f /root/.openclaw/workspace/health_monitor.pid
rm -f /root/.openclaw/workspace/supervisor.pid

# Kill any existing monitoring processes
pkill -f "health_monitor.sh" 2>/dev/null || true
pkill -f "container_supervisor.sh" 2>/dev/null || true

# Kill orphan containers
echo "Cleaning orphan containers..."
docker ps -aq --filter "name=freqtrade" --filter "status=exited" | xargs docker rm -f 2>/dev/null || true
docker ps -a | grep -E "(suspicious|busy|nostalgic)" | awk '{print $1}' | xargs docker rm -f 2>/dev/null || true

# Kill stuck download/backtest processes
pkill -f "download-data" 2>/dev/null || true
pkill -f "freqtrade backtest" 2>/dev/null || true

# Wait a moment
sleep 3

# Start the main bot if not running
if ! docker ps | grep -q "freqtrade-range"; then
    echo "Starting freqtrade-range..."
    cd /root/.openclaw/workspace/freqtrade
    docker compose up -d freqtrade-range 2>/dev/null || \
    docker run -d \
        --name freqtrade-range \
        --restart unless-stopped \
        -v /root/.openclaw/workspace/freqtrade/user_data:/freqtrade/user_data \
        -p 127.0.0.1:8082:8080 \
        freqtradeorg/freqtrade:stable trade \
        --logfile /freqtrade/user_data/logs/range.log \
        --db-url sqlite:////freqtrade/user_data/trades_range.sqlite \
        --config /freqtrade/user_data/config_range.json \
        --strategy MeanReversionScalper_v1
fi

echo "Bot started. Waiting 10 seconds..."
sleep 10

# Start health monitor
echo "Starting health monitor..."
/root/.openclaw/workspace/scripts/health_monitor.sh >> /root/.openclaw/workspace/logs/health_monitor.log 2>&1 &

# Start container supervisor
echo "Starting container supervisor..."
/root/.openclaw/workspace/scripts/container_supervisor.sh >> /root/.openclaw/workspace/logs/supervisor.log 2>&1 &

# Verify
sleep 5
echo ""
echo "=== STATUS CHECK ==="
docker ps --filter name=freqtrade --format "table {{.Names}}\t{{.Status}}"
echo ""
echo "Monitoring processes:"
ps aux | grep -E "health_monitor|container_supervisor" | grep -v grep | wc -l | xargs echo "Active monitors:"

echo ""
echo "=== SYSTEM READY ==="
echo "Health monitor PID: $(cat /root/.openclaw/workspace/health_monitor.pid 2>/dev/null || echo 'starting')"
echo "Logs: /root/.openclaw/workspace/logs/"
echo "Alerts will appear in: /root/.openclaw/workspace/logs/alerts.log"
