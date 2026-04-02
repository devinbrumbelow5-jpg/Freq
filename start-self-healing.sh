#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Self-Healing Agent Launcher (Daemon Mode)
# Freq Trading Swarm - Brownwood, Texas
# ═══════════════════════════════════════════════════════════════

WORKSPACE="/root/.openclaw/workspace"
SCRIPT="$WORKSPACE/self-healing-agent.sh"
LOG_DIR="$WORKSPACE/memory/logs"
PID_FILE="/tmp/self-healing-agent.pid"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

# Parse arguments first (before checking PID)
case "${1:-}" in
    --status)
        "$SCRIPT" --status
        exit 0
        ;;
    --stop)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE")
            if ps -p "$pid" > /dev/null 2>&1; then
                kill "$pid" 2>/dev/null
                sleep 1
            fi
            rm -f "$PID_FILE"
        fi
        # Also kill any orphaned processes
        pkill -f "self-healing-agent.sh" 2>/dev/null || true
        echo -e "${GREEN}✅ Self-healing agent stopped${NC}"
        exit 0
        ;;
    --logs)
        "$SCRIPT" --logs
        exit 0
        ;;
    --help|-h)
        echo "Self-Healing Agent Launcher"
        echo ""
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (none)    Start the monitoring agent"
        echo "  --status  Show container status and restart history"
        echo "  --stop    Stop the running agent"
        echo "  --logs    Follow the restart log"
        echo "  --help    Show this help message"
        exit 0
        ;;
esac

# Check if already running (after parsing args)
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE")
    if ps -p "$old_pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}Self-healing agent already running (PID: $old_pid)${NC}"
        echo ""
        echo "Commands:"
        echo "  $0 --status  # Check status"
        echo "  $0 --stop    # Stop the agent"
        echo "  $0 --logs    # View logs"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

echo -e "${GREEN}Starting Self-Healing Agent...${NC}"
echo ""

# Kill any orphaned processes first
pkill -f "self-healing-agent.sh" 2>/dev/null || true
sleep 0.5

# Start the agent with nohup, using SKIP_CHECK_RUNNING to bypass the check
# (since we're managing the PID ourselves)
nohup env SKIP_CHECK_RUNNING=1 "$SCRIPT" > "$LOG_DIR/healer.out" 2>&1 &
disown

# Wait a moment for the script to start and write its PID
sleep 2

# Get the actual PID (the background process we started)
HEALER_PID=$!
echo $HEALER_PID > "$PID_FILE"

# Verify it started
if ps -p "$HEALER_PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Self-healing agent started (PID: $HEALER_PID)${NC}"
    echo ""
    echo "Commands:"
    echo "  $0 --status  # Check container status"
    echo "  $0 --logs    # View restart log"
    echo "  $0 --stop    # Stop the agent"
    echo ""
    echo "Monitoring:"
    echo "  - freqtrade-main (Main trading bot)"
    echo "  - freqtrade-trend (Trend following bot)"
    echo "  - freqtrade-meanrev (Mean reversion bot)"
    echo "  - freqtrade-breakout (Breakout scalper bot)"
    echo "  - freqtrade-redis (Redis service)"
    echo "  - freqtrade-notifier (Notification service)"
    echo ""
    echo "Log file: $WORKSPACE/memory/restarts.log"
else
    echo -e "${RED}❌ Failed to start self-healing agent${NC}"
    cat "$LOG_DIR/healer.out" 2>/dev/null
    exit 1
fi