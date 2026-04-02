#!/bin/bash
# Stop Self-Healing Agent

PID_FILE="/tmp/self-healing-agent.pid"

if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "Stopping self-healing agent (PID: $pid)..."
        kill "$pid"
        rm -f "$PID_FILE"
        echo "✅ Self-healing agent stopped"
    else
        echo "Self-healing agent not running"
        rm -f "$PID_FILE"
    fi
else
    echo "Self-healing agent not running (no PID file found)"
fi