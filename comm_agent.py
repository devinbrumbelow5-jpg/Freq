#!/usr/bin/env python3
"""
Freq Communication Agent
Ensures stable WhatsApp/Telegram messaging
Runs as persistent background process
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime

WORKSPACE = "/root/.openclaw/workspace"
MEMORY_DIR = f"{WORKSPACE}/memory"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    with open(f"{MEMORY_DIR}/comm_agent.log", "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def check_containers():
    """Check container health"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        containers = {}
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                name, status = line.split('|', 1)
                containers[name] = status
        return containers
    except Exception as e:
        log(f"ERROR checking containers: {e}")
        return {}

def get_trading_stats():
    """Get P&L from main bot"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-u", "freqtrader:freqtrader", 
             "http://localhost:8080/api/v1/profit"],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        return {
            "trades": data.get("trade_count", 0),
            "profit": data.get("profit_all_percent", 0),
            "drawdown": data.get("max_drawdown", 0),
            "open": data.get("open_trade_count", 0)
        }
    except Exception as e:
        log(f"ERROR getting stats: {e}")
        return {"trades": 0, "profit": 0, "drawdown": 0, "open": 0}

def send_status_update():
    """Generate and send status update"""
    containers = check_containers()
    stats = get_trading_stats()
    
    freq_containers = {k: v for k, v in containers.items() if k.startswith("freqtrade-")}
    running = len([v for v in freq_containers.values() if "Up" in v])
    
    # Check for issues
    issues = []
    expected = ["freqtrade-redis", "freqtrade-notifier", "freqtrade-main",
                "freqtrade-trend", "freqtrade-meanrev", "freqtrade-breakout"]
    for exp in expected:
        if exp not in freq_containers:
            issues.append(f"{exp} MISSING")
        elif "Restarting" in freq_containers.get(exp, ""):
            issues.append(f"{exp} RESTARTING")
    
    # Build message
    msg_lines = [
        "⚡ FREQ STATUS UPDATE ⚡",
        f"Time: {datetime.now().strftime('%H:%M %Z')}",
        "",
        f"📊 Containers: {running}/6 running",
    ]
    
    if issues:
        msg_lines.append("⚠️ ISSUES DETECTED:")
        for issue in issues:
            msg_lines.append(f"  • {issue}")
    
    msg_lines.extend([
        "",
        "💰 Trading:",
        f"  • Trades: {stats['trades']}",
        f"  • Open: {stats['open']}",
        f"  • P&L: {stats['profit']:.2f}%",
        f"  • Drawdown: {stats['drawdown']:.2f}%",
        "",
        f"Mode: DRY-RUN | Status: {'✅ OK' if not issues else '⚠️ NEEDS ATTENTION'}"
    ])
    
    message = "\n".join(msg_lines)
    
    # Write to memory file (will be picked up by OpenClaw)
    with open(f"{MEMORY_DIR}/telegram_queue.txt", "w") as f:
        f.write(message)
    
    # Also write hourly update
    with open(f"{MEMORY_DIR}/hourly_update.txt", "w") as f:
        f.write(message)
    
    log(f"Status sent: {running}/6 containers, {stats['trades']} trades")
    return message

def healing_check():
    """Check if containers need restart"""
    containers = check_containers()
    expected = ["freqtrade-redis", "freqtrade-notifier", "freqtrade-main",
                "freqtrade-trend", "freqtrade-meanrev", "freqtrade-breakout"]
    
    restarted = []
    for exp in expected:
        if exp not in containers:
            log(f"HEALING: Starting {exp}")
            subprocess.run(
                ["docker", "compose", "-f", "/root/.openclaw/workspace/freqtrade/docker-compose.yml", 
                 "up", "-d", exp],
                capture_output=True, timeout=30
            )
            restarted.append(exp)
        elif "Restarting" in containers.get(exp, ""):
            log(f"HEALING: {exp} in restart loop, forcing recreate")
            subprocess.run(
                ["docker", "compose", "-f", "/root/.openclaw/workspace/freqtrade/docker-compose.yml",
                 "rm", "-sf", exp],
                capture_output=True, timeout=30
            )
            subprocess.run(
                ["docker", "compose", "-f", "/root/.openclaw/workspace/freqtrade/docker-compose.yml",
                 "up", "-d", exp],
                capture_output=True, timeout=30
            )
            restarted.append(exp)
    
    if restarted:
        log(f"Healed containers: {', '.join(restarted)}")
    
    return restarted

def main():
    log("=" * 50)
    log("FREQ COMMUNICATION AGENT STARTED")
    log("=" * 50)
    
    # Initial status
    send_status_update()
    
    last_hourly = datetime.now().hour
    cycle = 0
    
    while True:
        cycle += 1
        
        # Healing check every 60 seconds
        healing_check()
        
        # Hourly status update
        current_hour = datetime.now().hour
        if current_hour != last_hourly:
            send_status_update()
            last_hourly = current_hour
        
        # Every 5 minutes, log heartbeat
        if cycle % 5 == 0:
            containers = check_containers()
            running = len([v for v in containers.values() if "Up" in v])
            log(f"Heartbeat: {running} containers running")
        
        time.sleep(60)

if __name__ == "__main__":
    os.makedirs(MEMORY_DIR, exist_ok=True)
    main()
