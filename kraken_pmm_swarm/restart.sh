#!/bin/bash
cd /root/.openclaw/workspace/kraken_pmm_swarm
source venv/bin/activate
nohup python main.py > logs/swarm_passive_$(date +%Y%m%d_%H%M%S).log 2>&1 &
echo $! > swarm.pid
echo "Started PMM Swarm with PID: $!"
