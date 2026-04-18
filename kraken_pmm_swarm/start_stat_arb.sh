#!/bin/bash
cd /root/.openclaw/workspace/kraken_pmm_swarm
source venv/bin/activate
python stat_arb.py > logs/stat_arb_$(date +%Y%m%d_%H%M%S).log 2>&1 &
echo $! > stat_arb.pid
echo "Stat Arb Engine started with PID: $!"
