#!/bin/bash
# Self-Healing Agent for Freq Ultimate Scalper v2.0
# Runs every 5 minutes via cron

WORKSPACE="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/self_healing.log"
MEMORY_DIR="$WORKSPACE/memory"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Self-Healing Check Started ==="

# 1. Check if containers are running
CONTAINERS=("freqtrade-grid" "freqtrade-range" "freqtrade-breakout" "freqtrade-regime-filter")
RESTARTED=0

for container in "${CONTAINERS[@]}"; do
    if ! docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        log "⚠️ Container $container not running - restarting"
        cd "$WORKSPACE/freqtrade"
        docker start "$container" 2>/dev/null || docker-compose up -d "$container" 2>/dev/null
        RESTARTED=$((RESTARTED+1))
    fi
done

if [ $RESTARTED -eq 0 ]; then
    log "✅ All containers running"
fi

# 2. Check for zombie processes
ZOMBIES=$(ps aux | grep -E "drawdown_regime_guard|kimi_trading_brain" | grep -v grep | wc -l)
if [ "$ZOMBIES" -gt 2 ]; then
    log "⚠️ Found $ZOMBIES regime guard processes - cleaning up"
    pkill -9 -f drawdown_regime_guard.py 2>/dev/null
    pkill -9 -f kimi_trading_brain.py 2>/dev/null
    sleep 2
    # Restart with flock
    flock -n /tmp/regime_guard.lock -c "python3 $WORKSPACE/scripts/drawdown_regime_guard.py" >> $WORKSPACE/logs/regime_guard_cron.log 2>&1 &
fi

# 3. Check if kimi brain is running
if ! pgrep -f "kimi_trading_brain.py" > /dev/null; then
    log "⚠️ Kimi Trading Brain not running - starting"
    python3 "$WORKSPACE/kimi_trading_brain.py" >> $WORKSPACE/logs/kimi_brain.log 2>&1 &
fi

# 4. Run kimi brain once for stats
log "📊 Running swarm stats check"
python3 "$WORKSPACE/kimi_trading_brain.py" --once > "$MEMORY_DIR/swarm_check.json" 2>/dev/null

# 5. Check disk space
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    log "🚨 WARNING: Disk usage at ${DISK_USAGE}%"
    # Clean old logs
    find "$WORKSPACE/logs" -name "*.log" -size +50M -exec truncate -s 50M {} \;
fi

# 6. Check for pause file
if [ -f "/tmp/pause_swarm" ]; then
    log "⏸️ Swarm is PAUSED ($(cat /tmp/pause_swarm | head -1))"
fi

# 7. Check if live mode is enabled
if [ -f "/tmp/enable_live" ]; then
    log "🔴 LIVE MODE ENABLED ($(cat /tmp/enable_live | head -1))"
fi

log "=== Self-Healing Check Complete ==="
echo ""