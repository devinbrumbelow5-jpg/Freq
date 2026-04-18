# HEARTBEAT.md - Kraken PMM Swarm
## Multi-Tier Proactive Heartbeat System for Passive Market Making
**Execution Model:** OpenClaw cron jobs + PMM swarm coordination  
**Location:** Brownwood, Texas  
**Timezone:** America/Chicago (Central Time)  
**Dependencies:** Python 3.11, CCXT Pro WebSocket, SQLite, asyncio  
**System:** Kraken PMM Swarm (CCXT-based Passive Market Making)

**All timestamps in Central Time (CT/CDT).**

---

## Architecture Overview

**Active System:** Kraken PMM Swarm
- **Main Process:** `main.py` (PID tracked at runtime)
- **Bots:** 3 passive market makers (BTC/USD, ETH/USD, SOL/USD)
- **Strategy:** Aggressive PMM with tight spreads (1.5-2.5 bps)
- **Database:** `coinbase_swarm.db` (SQLite)
- **Paper Balance:** $6,000 USD simulated

**Key Files:**
- `kraken_pmm_swarm/main.py` - Entry point
- `kraken_pmm_swarm/coinbase_swarm.db` - Trade/position data
- `kraken_pmm_swarm/config_aggressive.yaml` - Active config
- `kraken_pmm_swarm/logs/` - Application logs

---

## Tier 1: Rapid Response (Every 30 Seconds)

**Purpose:** Real-time PMM monitoring and risk management

### Risk Guardian Check
```bash
# Execute via OpenClaw cron every 30s
*/30 * * * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/pmm_risk_check.py"
```

**Script Actions:**
1. Check main.py process is running (PID from ps)
2. Query `coinbase_swarm.db` for bot status
3. Calculate total position exposure across all bots
4. Check inventory skew limits (>50% = risk)
5. Verify WebSocket connections (order book freshness)
6. **IF total exposure > $3,000 (50%):** Trigger position reduction
7. **IF inventory skew > 0.8 for any bot:** Alert + force rebalancing
8. **IF process down:** Auto-restart with same config

**Risk Thresholds:**
| Metric | Threshold | Action |
|--------|-----------|--------|
| Total Exposure | >50% of $6K | Reduce position sizes |
| Inventory Skew | >0.8 | Force rebalancing orders |
| WebSocket Stale | >10s | Reconnect + alert |
| Process Down | - | Auto-restart immediately |

**Memory Write:** `memory/pmm_risk_metrics.json`

---

## Tier 2: 5-Minute Operational Check

**Purpose:** Bot health, fills tracking, performance snapshot

```bash
*/5 * * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/pmm_health_check.py"
```

**Script Actions:**
1. Query `bot_status` table for all 3 bots
2. Count fills in last 5 minutes
3. Calculate P&L per bot (realized + unrealized)
4. Check spread competitiveness vs market
5. Log any errors from `logs/coinbase_swarm.log`

**Metrics Tracked:**
- Bot status (running/stopped)
- Current bid/ask per pair
- Position size per bot
- Fills count (5min window)
- Realized P&L (session total)
- Spread vs market spread

**Decision Logic:**
```python
if fills_5min == 0:
    CHECK_MARKET_SPREAD()  # May be uncompetitive
    
if realized_pnl < -100:  # -$100 threshold
    ALERT("Significant loss detected")
    
if spread_market > spread_bot * 2:
    ALERT("Spread too tight, missing fills")
```

**Memory Write:** `memory/pmm_health_5min.json`

---

## Tier 3: 1-Hour Performance Review

**Schedule:** Every hour (top of hour)  
**Duration:** 2-5 minutes

### Hourly P&L Analysis
```bash
0 * * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/pmm_hourly_report.py"
```

**Script Actions:**
1. Query fills from last hour
2. Calculate:
   - Total maker fees paid
   - Gross P&L (fills * edge)
   - Net P&L (after fees)
   - Fill rate (orders placed vs filled)
   - Inventory turnover
3. Compare vs targets

**Target Metrics:**
| Metric | Target | Action if Missed |
|--------|--------|------------------|
| Hourly Net P&L | >$1 | Review spreads |
| Fill Rate | >15% | Widen spreads |
| Inventory Turnover | 2-4x/day | Adjust sizes |
| Avg Edge | >2 bps | Check competition |

**Memory Write:** `memory/pmm_hourly_YYYY-MM-DD_HH.json`

---

## Tier 4: 4-Hour Strategy Optimization

**Schedule:** Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)  
**Duration:** 5-10 minutes

### Phase 1: Data Analysis (0-3 min)
```bash
openclaw exec "sqlite3 /root/.openclaw/workspace/kraken_pmm_swarm/coinbase_swarm.db 'SELECT pair, COUNT(*) as fills, AVG(price) as avg_price, SUM(amount) as volume FROM fills WHERE filled_at > datetime(\"now\", \"-4 hours\") GROUP BY pair;'"
```

**Analysis:**
- Best/worst performing pairs
- Volume distribution
- Price trend during MM activity

### Phase 2: Spread Optimization (3-6 min)
```python
# Dynamic spread adjustment based on:
# - Fill rate (increase if <10%, decrease if >30%)
# - Market volatility (widen in high vol)
# - Competition (match or beat top of book)

if fill_rate < 0.10:
    new_spread = current_spread * 0.9  # Tighten
elif fill_rate > 0.30:
    new_spread = current_spread * 1.1  # Widen
```

**Config Update:** `config_aggressive.yaml`

### Phase 3: Database Backup (6-8 min)
```bash
cp /root/.openclaw/workspace/kraken_pmm_swarm/coinbase_swarm.db /root/.openclaw/workspace/kraken_pmm_swarm/backups/coinbase_swarm_$(date +%Y%m%d_%H%M%S).db
```

### Phase 4: Hot-Reload (8-10 min)
```bash
# Signal running process to reload config
# Or restart if spread changes significant
```

**Memory Write:** `memory/pmm_optimization_4h.json`

---

## Tier 5: Daily Strategic Review

**Schedule:** 00:00 daily  
**Duration:** 10-15 minutes

### Daily Report Generation
```bash
0 0 * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/pmm_daily_report.py"
```

**Report Contents:**
```json
{
  "date": "2026-04-17",
  "session_pnl": {
    "gross": "+45.23",
    "fees": "-12.50",
    "net": "+32.73"
  },
  "fills": {
    "total": 234,
    "buy": 118,
    "sell": 116
  },
  "bots": {
    "BTC/USD": {"fills": 89, "pnl": "+12.40"},
    "ETH/USD": {"fills": 87, "pnl": "+14.20"},
    "SOL/USD": {"fills": 58, "pnl": "+6.13"}
  },
  "avg_spread_captured": "2.8 bps",
  "inventory_turnover": "3.2x",
  "best_hour": "14:00-15:00",
  "worst_hour": "03:00-04:00"
}
```

**Actions:**
- Archive daily report to `memory/pmm_daily_YYYY-MM-DD.json`
- Compare to previous day
- Adjust strategy if 3-day trend negative
- Rotate logs if >100MB

---

## Emergency Protocols

### Total Exposure > $3,500 (Critical)
```python
# Immediate position reduction
for bot in bots:
    if bot.position_value > bot.max_position * 0.8:
        bot.reduce_position(by=50%)
        ALERT("Critical exposure: {} reduced".format(bot.pair))
```

### Process Crash
```bash
# Auto-restart with monitoring
if ! pgrep -f "main.py"; then
    cd /root/.openclaw/workspace/kraken_pmm_swarm
    nohup venv/bin/python main.py > logs/restart_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    ALERT("PMM Swarm restarted after crash")
fi
```

### WebSocket Disconnect > 30s
```python
# Fallback to REST polling
if ws_latency > 30:
    SWITCH_TO_REST_FALLBACK()
    NOTIFY("WebSocket down, using REST")
```

---

## File Structure

```
/root/.openclaw/workspace/
├── kraken_pmm_swarm/
│   ├── main.py                 # Entry point
│   ├── swarm_manager.py        # Bot orchestration
│   ├── pmm_bot.py              # Individual bot logic
│   ├── coinbase_paper_client.py # CCXT Pro + paper trading
│   ├── aggressive_mm.py        # Aggressive PMM strategy
│   ├── database.py             # SQLite interface
│   ├── coinbase_swarm.db       # LIVE DATABASE
│   ├── config_aggressive.yaml  # ACTIVE CONFIG
│   ├── logs/
│   │   └── coinbase_swarm.log  # Application logs
│   └── backups/                # DB backups
├── memory/
│   ├── pmm_risk_metrics.json   # 30s updates
│   ├── pmm_health_5min.json    # 5min updates
│   ├── pmm_hourly_*.json       # Hourly reports
│   ├── pmm_optimization_4h.json # 4h optimization
│   └── pmm_daily_*.json          # Daily reports
└── scripts/
    ├── pmm_risk_check.py       # 30s risk check
    ├── pmm_health_check.py     # 5min health
    ├── pmm_hourly_report.py    # Hourly report
    └── pmm_daily_report.py      # Daily report
```

---

## OpenClaw Scheduling

```python
# 30s rapid risk monitoring
cron: {
  "action": "add",
  "job": {
    "name": "pmm-risk-30s-check",
    "schedule": {"kind": "every", "everyMs": 30000},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute 30s PMM risk check"
    }
  }
}

# 5min health check
cron: {
  "action": "add",
  "job": {
    "name": "pmm-health-5min",
    "schedule": {"kind": "every", "everyMs": 300000},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute 5min PMM health check"
    }
  }
}

# Hourly report
cron: {
  "action": "add",
  "job": {
    "name": "pmm-hourly-report",
    "schedule": {"kind": "cron", "expr": "0 * * * *"},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute hourly PMM report"
    }
  }
}

# 4h optimization
cron: {
  "action": "add",
  "job": {
    "name": "pmm-4h-optimization",
    "schedule": {"kind": "cron", "expr": "0 */4 * * *"},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute 4h PMM optimization"
    }
  }
}
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily Net P&L | >$20/day | Session total |
| Fill Rate | 15-25% | Fills/Orders |
| Avg Spread | 2-3 bps | vs mid-market |
| Inventory Turnover | 2-4x/day | Position churn |
| Uptime | >99% | Process monitoring |
| WebSocket Latency | <500ms | Order book freshness |

---

## Current Status

**Version:** 1.0.0 — PMM Swarm  
**Last Updated:** 2026-04-17  
**Execution Status:** ACTIVE  
**Process:** PID 3,281,477 (main.py)  
**Database:** coinbase_swarm.db  
**Config:** config_aggressive.yaml

---

_Kraken PMM Swarm — Local. Passive. Relentlessly Profitable._
