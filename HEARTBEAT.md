# HEARTBEAT.md - Freq Ultimate Scalper v2.0

## Multi-Tier Proactive Heartbeat System for High-Frequency Scalping

**Execution Model:** OpenClaw cron jobs + 6-agent swarm coordination  
**Location:** Local hardware (Brownwood, Texas)  
**Dependencies:** Docker, Freqtrade with CCXT Pro, SQLite, Redis (optional), local GPU  
**Latency Target:** <200ms for all data feeds

---

## Tier 1: Ultra-Rapid Response (Every 15 Seconds)

**Purpose:** Real-time scalping monitoring and emergency response

### Risk Guardian + Latency Monitor
```bash
# Execute via OpenClaw cron every 15s
*/15 * * * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/scalping_risk_check.py"
```

**Script Actions:**
1. Query current positions from SQLite
2. Calculate real-time drawdown
3. Check total exposure vs 6% limit
4. **NEW:** Check average latency of websocket feeds (<200ms?)
5. **NEW:** Monitor fill quality (slippage analysis)
6. **NEW:** Check for stale data (last tick timestamp)
7. **IF drawdown > 10%:** Trigger immediate alert
8. **IF drawdown > 12%:** Execute emergency stop
9. **IF latency > 300ms for 60s:** Alert + switch to REST fallback

**Memory Write:** `memory/risk_metrics.json`, `memory/latency_current.json`

---

## Tier 2: 4-Hour Self-Improvement Cycle (CRITICAL)

**Schedule:** Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)  
**Duration:** 20-40 minutes (scalping requires more analysis)  
**Purpose:** Complete system optimization, scalping strategy tuning, FreqAI retraining

### Phase 1: Data Refresh + Websocket Health (0-5 min)
```bash
openclaw exec "cd /root/.openclaw/workspace/freqtrade && docker-compose exec freqtrade freqtrade download-data --exchange binance --pairs BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,UNI/USDT,AAVE/USDT,LDO/USDT,CRV/USDT,SUSHI/USDT --timeframes 15s,1m,5m,15m,1h --timerange $(date -d '16 days ago' +%Y%m%d)-$(date +%Y%m%d)"
```

**Actions:**
1. Download OHLCV for all pairs (15s, 1m, 5m critical)
2. Verify websocket health (reconnect if stale >30s)
3. Update order-book snapshots
4. **NEW:** Log latency histograms

**Memory Write:** `memory/data_refresh.json`, `memory/websocket_health.json`

### Phase 2: Scalping P&L Analysis (5-10 min)
```bash
openclaw exec "sqlite3 /root/.openclaw/workspace/freqtrade/tradesv3.dryrun.sqlite 'SELECT pair, COUNT(*) as trades, AVG(profit_ratio) as avg_profit, SUM(profit_ratio) as total_profit, AVG(fee_ratio) as avg_fee FROM trades WHERE close_date > datetime(\"now\", \"-4 hours\") GROUP BY pair;'"
```

**Metrics Calculated:**
- Profit factor (last 4h) — SCALPING TARGET: >1.6
- Win rate (last 4h) — SCALPING TARGET: >48%
- Sharpe ratio (last 4h) — SCALPING TARGET: >2.0
- Max drawdown (last 4h)
- **NEW:** Average trade duration (scalping: 30s-10min target)
- **NEW:** Slippage vs expected (per trade)
- **NEW:** Fee impact analysis
- Best/worst performing pairs
- Strategy effectiveness per timeframe

**Decision Logic:**
```python
if profit_factor < 1.6:
    TRIGGER("hyperopt_aggressive_scalping")
elif avg_trade_duration > 600:  # 10 minutes
    TRIGGER("tighten_exits")
elif slippage_avg > 0.05:  # 5 bps
    TRIGGER("review_execution")
else:
    LOG("Scalping performance acceptable: PF={}, duration={}s", profit_factor, avg_duration)
```

**Memory Write:** `memory/scalping_pnl.json`

### Phase 3: Scalping Regime Detection (10-15 min)
```bash
openclaw exec "python3 /root/.openclaw/workspace/scripts/detect_scalping_regime.py"
```

**Script Actions:**
1. Calculate volatility on 15s/1m/5m timeframes
2. Calculate order-book depth imbalance
3. Calculate trade flow (buy/sell pressure)
4. Detect scalping regime:
   - **HIGH_VOL_HIGH_LIQUIDITY** → Aggressive micro-scalping
   - **LOW_VOL_TIGHT_SPREAD** → Range scalping
   - **BREAKOUT_BUILDING** → Prepare momentum capture
   - **CHOPPY_ILLIQUID** → Reduce size, widen stops
5. Compare to previous regime

**Regime Shift Detection:**
```python
if current_regime != previous_regime:
    TRIGGER("scalping_strategy_rotation")
    LOG(f"Scalping regime shift: {previous_regime} -> {current_regime}")
```

**Memory Write:** `memory/scalping_regime.json`

### Phase 4: FreqAI Model Retraining (15-25 min)
```bash
openclaw exec "cd /root/.openclaw/workspace/freqtrade && docker-compose exec freqtrade freqtrade trade --config user_data/config_scalping.json --strategy FreqAI_Scalper_v1 --freqaimodel LightGBMClassifier --force-buy"
```

**Training Parameters (Scalping-Specific):**
- `train_period_days`: 7 (shorter for scalping relevance)
- `backtest_period_days`: 3
- `live_retrain_hours`: 4
- `continual_learning`: true
- `n_estimators`: 500 (higher for micro-patterns)
- `learning_rate`: 0.03
- **NEW:** Features: order_book_imbalance, trade_flow, volatility_15s, spread_pct

**Validation:**
- Check model files updated
- Verify prediction latency (<50ms)
- Confirm no training errors
- **NEW:** Backtest model on last 24h unseen data

**Memory Write:** `memory/freqai_scalping_retrain.json`

### Phase 5: Hyperopt for Scalping (Conditional, 25-35 min)
**Trigger:** If profit_factor < 1.6 OR avg_duration > 10min OR performance dropped >5%

```bash
openclaw exec "cd /root/.openclaw/workspace/freqtrade && docker-compose exec freqtrade freqtrade hyperopt --strategy FreqAI_Scalper_v1 --freqaimodel LightGBMClassifier -e 500 --spaces buy sell roi trailing stoploss --hyperopt-loss SharpeHyperOptLossDaily --timerange $(date -d '7 days ago' +%Y%m%d)-$(date +%Y%m%d)"
```

**Scalping-Specific Optimization:**
- Entry thresholds (tighter for scalping)
- Exit timeouts (shorter)
- Trailing stop distance (closer)
- Position sizing based on spread

**Memory Write:** `memory/hyperopt_scalping_results.json`

### Phase 6: Strategy Rotation (35-40 min)
**Trigger:** Regime shift OR hyperopt completed

```bash
openclaw exec "python3 /root/.openclaw/workspace/scripts/rotate_scalping_strategy.py --regime $(cat /root/.openclaw/workspace/memory/scalping_regime.json | jq -r '.regime')"
```

**Scalping Strategy Rotation:**
- **HIGH_VOL_HIGH_LIQUIDITY** → MicroBreakout_v1 (aggressive)
- **LOW_VOL_TIGHT_SPREAD** → RangeMeanReversion_pro
- **BREAKOUT_BUILDING** → MomentumSnap (prepared)
- **CHOPPY_ILLIQUID** → Reduce to 1-2 pairs, widen stops

**Memory Write:** `memory/scalping_strategy_rotation.json`

### Phase 7: Verification (40-45 min)
```bash
openclaw exec "cd /root/.openclaw/workspace && ./scripts/verify_scalping_cycle.sh"
```

**Checks:**
- [ ] All containers running
- [ ] Websockets connected (all pairs)
- [ ] Avg latency <200ms
- [ ] Database accessible
- [ ] FreqAI models updated
- [ ] No error logs in last hour
- [ ] Drawdown < 6%
- [ ] API responding on port 8080

**Memory Write:** `memory/cycle_verification.json`

---

## Tier 3: 12-Hour Deep Scalping Analysis

**Schedule:** 00:00 and 12:00  
**Duration:** 45-60 minutes  
**Purpose:** Walk-forward backtesting, slippage analysis, strategy validation

```bash
0 0,12 * * * openclaw exec "cd /root/.openclaw/workspace/freqtrade && ./scripts/full_scalping_backtest.sh"
```

**Backtest Steps:**
1. Walk-forward on 15s/1m/5m data (90 days)
2. Monte-Carlo simulation for slippage
3. Fee impact at realistic maker/taker rates
4. Fill probability analysis

**Target Metrics:**
- Sharpe > 2.0
- Max drawdown < 8%
- Win rate > 48%
- Avg duration 30s-5min
- Profit factor > 1.6

**Memory Writes:**
- `memory/scalping_backtest_12h.json`
- `memory/slippage_analysis.json`
- `memory/strategy_health.json`

---

## Tier 4: 24-Hour Strategic Review

**Schedule:** 00:00 daily  
**Duration:** 15-20 minutes

### Daily Scalping Report
```bash
0 0 * * * openclaw exec "cd /root/.openclaw/workspace && python3 scripts/daily_scalping_report.py"
```

**Report Contents:**
```json
{
  "date": "2026-03-30",
  "daily_pnl": "+0.67%",
  "cumulative_pnl": "+18.23%",
  "max_drawdown": "3.8%",
  "sharpe_ratio": "2.34",
  "win_rate": "52%",
  "profit_factor": "1.78",
  "trades_today": 87,
  "avg_trade_duration": "2m 34s",
  "avg_latency_ms": 142,
  "total_fees_paid": "0.12%",
  "net_after_fees": "+0.55%",
  "best_pair": "SOL/USDT (+1.2%)",
  "worst_pair": "LDO/USDT (-0.3%)",
  "regime_changes": 4,
  "hyperopt_runs": 3,
  "freqai_retrains": 6,
  "slippage_avg_bps": 3.2
}
```

**Memory Write:** `memory/daily_scalping_report_YYYYMMDD.json`

---

## Emergency Protocols (Immediate Execution)

### Drawdown > 10%
```python
exec: {
  "command": "echo '🚨 CRITICAL: Drawdown 10.2% - Approaching 12% limit' && curl -s http://localhost:8080/api/v1/status"
}
exec: {
  "command": "cd /root/.openclaw/workspace/freqtrade && docker-compose exec freqtrade freqtrade forcesell all"
}
```

### Latency Spike > 500ms (60s sustained)
```python
exec: {
  "command": "echo '⚠️ HIGH LATENCY: {}ms - Switching to REST fallback'.format(latency) && python3 scripts/switch_to_rest_fallback.py"
}
```

### Websocket Disconnect > 30s
```python
exec: {
  "command": "python3 scripts/emergency_websocket_reconnect.py && alert_telegram 'Websocket reconnect executed'"
}
```

### API Rate Limit Hit
```python
exec: {
  "command": "python3 scripts/backoff_and_resume.py --duration 60"
}
```

---

## OpenClaw Scheduling

```python
# 15s rapid monitoring
cron: {
  "action": "add",
  "job": {
    "name": "freq-scalping-15s-check",
    "schedule": {"kind": "every", "everyMs": 15000},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute 15s scalping risk + latency check"
    }
  }
}

# 4h full cycle
cron: {
  "action": "add",
  "job": {
    "name": "freq-4h-scalping-cycle",
    "schedule": {"kind": "cron", "expr": "0 */4 * * *"},
    "payload": {
      "kind": "systemEvent",
      "text": "Execute 4-hour scalping self-improvement cycle"
    }
  }
}
```

---

## Success Metrics (Scalping)

After 30 days:
- **Profit Factor:** > 1.6
- **Sharpe Ratio:** > 2.0
- **Max Drawdown:** < 8%
- **Win Rate:** > 48%
- **Avg Latency:** < 200ms
- **Avg Trade Duration:** 30s-5min
- **Net Daily Return:** > 0.5%
- **Uptime:** > 98%

---

**Version:** 2.0.0 — ULTIMATE SCALPER  
**Last Updated:** 2026-03-29  
**Execution Status:** SWARM ACTIVATING

_Freq Ultimate Scalper — Local. Fast. Ruthlessly Profitable._
