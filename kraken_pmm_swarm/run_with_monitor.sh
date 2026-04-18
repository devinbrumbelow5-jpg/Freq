#!/bin/bash
# PMM Swarm with Auto-Restart Monitor - CENTRAL TIME
# All timestamps in America/Chicago (Central Time)

export TZ='America/Chicago'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kill any existing monitor or main processes
pkill -9 -f "python.*monitor.py" 2>/dev/null
pkill -9 -f "python.*main.py" 2>/dev/null
sleep 2

# Start the monitor (which manages the swarm)
echo "[$(date '+%Y-%m-%d %H:%M:%S CT')] Starting PMM Swarm Monitor..."

# Create log with CT timestamp
LOGFILE="logs/monitor_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

nohup venv/bin/python monitor.py > "$LOGFILE" 2>&1 &
echo $! > monitor.pid

echo "[$(date '+%Y-%m-%d %H:%M:%S CT')] Monitor started."
echo "Monitor PID: $(cat monitor.pid)"
echo "Log file: $LOGFILE"
echo "Database: coinbase_swarm.db"
echo "Timezone: $(date +%Z)"
