#!/bin/bash
# Start EMA Swarm with proper logging

cd /root/.openclaw/workspace/kraken_pmm_swarm

echo "=========================================="
echo "Starting CCXT EMA Swarm - $(date)"
echo "=========================================="

export PYTHONUNBUFFERED=1
./venv/bin/python run_ema_fixed.py 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%H:%M:%S')] $line"
done
