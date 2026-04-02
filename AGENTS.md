# AGENTS.md - Freq Ultimate Scalper v2.0

## Swarm Architecture

Freq operates as a **decentralized swarm of 6 specialized agents**, now fully optimized for HIGH-FREQUENCY SCALPING with sub-5-minute trade durations and <200ms latency targets.

---

## Agent Definitions

### 1. Market Analyst 🎯
**Role:** Real-time market regime detection and LIVE data ingestion

**Responsibilities:**
- Monitor 10 high-volume pairs continuously (BTC/USDT, ETH/USDT, SOL/USDT, AVAX/USDT, LINK/USDT, UNI/USDT, AAVE/USDT, LDO/USDT, CRV/USDT, SUSHI/USDT)
- **SCALPING ENHANCED:** Pull 15s/1m/5m OHLCV via CCXT
- **NEW:** Maintain websocket connections for real-time tickers, order-books (L2), trades
- **NEW:** Calculate latency metrics on every tick (<200ms target)
- Detect scalping regime (HIGH_VOL_HIGH_LIQUIDITY, LOW_VOL_TIGHT_SPREAD, BREAKOUT_BUILDING, CHOPPY_ILLIQUID)
- Calculate micro-volatility (ATR on 15s), spread %, order-book imbalance
- Publish `scalping_regime` to memory/

**Decision Triggers:**
- If volatility (15s ATR) > 0.1%: Signal "HIGH_VOL_HIGH_LIQUIDITY"
- If spread < 0.05% AND volume steady: Signal "LOW_VOL_TIGHT_SPREAD"
- If order-book imbalance > 2:1 for 10s: Signal "BREAKOUT_BUILDING"
- If latency > 300ms for 60s: Signal "LATENCY_DEGRADED" to Risk Guardian

**Memory Writes:**
- `memory/scalping_regime.json` - Current scalping regime
- `memory/websocket_health.json` - Connection status, latency per pair
- `memory/order_book_snapshots.json` - Latest L2 data
- `memory/latency_histogram.json` - 15s/1m/5m/15m latency stats

---

### 2. Strategy Generator 🧠
**Role:** Adaptive SCALPING strategy selection and micro-parameter tuning

**Responsibilities:**
- Read `scalping_regime.json` every 15s
- Select optimal scalping strategy for current regime:
  - **HIGH_VOL_HIGH_LIQUIDITY** → MicroBreakout_v1 (15s-1m timeframe)
  - **LOW_VOL_TIGHT_SPREAD** → RangeMeanReversion_pro (1m-5m, tight stops)
  - **BREAKOUT_BUILDING** → MomentumSnap (1m-3m, volume spike entry)
  - **CHOPPY_ILLIQUID** → Reduce size 50%, widen stops, fewer pairs
- Generate scalping-specific configs with dynamic parameters
- Trigger Hyperopt Engineer when regime changes OR performance degrades

**SCALPING Strategies:**

1. **MicroBreakout_v1** (Primary for high-vol)
   - Entry: 15s candle close above 3-period EMA + volume > 1.5x average
   - Exit: 0.3% profit target or 0.15% stop
   - Duration: 30s-3min target

2. **RangeMeanReversion_pro** (For low-vol, tight spreads)
   - Entry: Price touches lower Bollinger (1m) + RSI < 30
   - Exit: Middle band OR 0.25% profit
   - Duration: 2-10min target

3. **MomentumSnap** (For breakouts)
   - Entry: 1m EMA cross + trade flow imbalance > 2:1
   - Exit: Trailing stop 0.2% or momentum fade
   - Duration: 1-5min target

4. **OrderFlowScalper** (Advanced, requires order-book)
   - Entry: Bid/ask pressure shift + large limit order placement
   - Exit: Opposite flow OR time-based (30s max)
   - Duration: 10s-2min target

5. **FreqAI_Scalper_v1** (ML-enhanced)
   - Entry: LightGBM prediction > 0.6 confidence + signal confirmation
   - Exit: Prediction decay OR stop
   - Duration: Varies based on model

**Decision Logic:**
```python
IF regime == "HIGH_VOL_HIGH_LIQUIDITY":
    ACTIVATE(MicroBreakout_v1, position_size=1.0x)
    CALL HyperoptEngineer.optimize("micro_breakout_params")
    
ELIF regime == "LOW_VOL_TIGHT_SPREAD":
    ACTIVATE(RangeMeanReversion_pro, position_size=0.8x)
    
ELIF regime == "BREAKOUT_BUILDING":
    ACTIVATE(MomentumSnap, position_size=1.2x)
    PREPARE(OrderFlowScalper)
    
ELIF regime == "CHOPPY_ILLIQUID":
    REDUCE_ALL_SIZES(by=50%)
    BLOCK_NEW_ENTRIES(duration=300s)
    NOTIFY("Low quality regime - reduced exposure")
    
IF avg_trade_duration > 600s:  # 10 minutes
    TRIGGER("tighten_exits")
```

**Memory Writes:**
- `memory/active_scalping_strategy.json` - Current strategy per pair
- `memory/scalping_params.json` - Dynamic parameters (entry/exit thresholds)
- `memory/regime_history.json` - Regime transitions (for backtesting)

---

### 3. Hyperopt Engineer 🔬
**Role:** Continuous SCALPING hyperparameter optimization

**Responsibilities:**
- Run hyperopt every 4 hours on last 7 days of 15s/1m/5m data
- **SCALPING FOCUS:** Optimize for tight profit targets, fast exits, fee efficiency
- Generate 100 epochs minimum, 500 epochs for major regime shifts
- **NEW:** Optimize for net profit AFTER fees (maker/taker simulation)
- Save winning parameters to `user_data/hyperopts/`
- Trigger hot-reload via Executor

**Hyperopt Scope (Scalping-Specific):**
- Entry signals (EMA periods 3-10, RSI thresholds 20-40, volume multiplier 1.2-2.5)
- Exit signals (profit target 0.1-0.5%, stop 0.05-0.2%)
- Position sizing (stake amount, max 3 concurrent per strategy)
- Timeframe preferences (15s vs 1m vs 5m based on volatility)
- **NEW:** Spread tolerance (skip if spread > threshold)
- **NEW:** Latency threshold (abort if feed stale)

**Decision Logic:**
```python
IF current_profit_factor < 1.6 OR avg_trade_duration > 600s:
    RUN aggressive_hyperopt(epochs=500, timerange="last_14_days")
    
ELIF slippage_avg > 0.05:  # 5 bps
    RUN execution_hyperopt(epochs=200, focus="fill_quality")
    
ELSE:
    RUN maintenance_hyperopt(epochs=100, timerange="last_7_days")
```

**Memory Writes:**
- `memory/scalping_hyperopt_results.json` - Winning parameters
- `memory/scalping_optimization_log.json` - All epochs, losses
- `memory/performance_delta.json` - Before/after metrics

---

### 4. Risk Guardian 🛡️
**Role:** Capital protection and SCALPING-specific exposure management

**Responsibilities:**
- Monitor total exposure every 15 seconds (faster for scalping)
- Calculate real-time drawdown vs peak equity
- **NEW:** Monitor latency on every tick (<200ms target)
- **NEW:** Track fill quality and slippage per trade
- **NEW:** Circuit breaker on websocket degradation
- Enforce position limits (max 6% total exposure, max 6 concurrent trades)
- Monitor correlation risk (no more than 3 correlated pairs)
- **EMERGENCY STOP** if drawdown exceeds 12%

**Risk Metrics (Calculated Every 15s):**
- `total_exposure`: Sum of all open position values
- `current_drawdown`: (Peak_Equity - Current_Equity) / Peak_Equity
- `portfolio_heat`: Weighted volatility of open positions
- `correlation_risk`: Max correlation between any 2 open pairs
- **NEW:** `avg_latency_ms`: Average websocket latency
- **NEW:** `fill_slippage_bps`: Average execution slippage
- **NEW:** `stale_feed_count`: Ticks > 5s old

**Decision Protocols:**
```python
IF current_drawdown > 0.12 (12%):
    EMERGENCY_STOP_ALL()
    ALERT("CRITICAL: 12% drawdown breached. All positions closed.")

IF total_exposure > 0.06 (6% of portfolio):
    BLOCK_NEW_ENTRIES()
    NOTIFY("Max exposure reached. No new positions.")

IF avg_latency_ms > 300 FOR 60s:
    SWITCH_TO_REST_FALLBACK()
    NOTIFY("High latency detected. Switched to REST API.")

IF fill_slippage_bps > 10:
    REDUCE_POSITION_SIZES(by=30%)
    NOTIFY("High slippage detected. Reduced sizing.")

IF stale_feed_count > 10:
    EMERGENCY_WEBSOCKET_RECONNECT()
    NOTIFY("Stale data detected. Reconnecting websockets.")

IF correlation_risk > 0.8 AND position_count > 2:
    CLOSE_HIGHEST_CORRELATED_PAIR()
    NOTIFY("Correlation risk reduced via pair closure.")
```

**Authority:** Can override ANY other agent's decision. Risk Guardian decisions are absolute.

**Memory Writes:**
- `memory/scalping_risk_metrics.json` - Real-time exposure + latency data
- `memory/drawdown_log.json` - Historical drawdowns
- `memory/slippage_log.json` - Fill quality tracking
- `memory/emergency_stops.json` - All emergency interventions

---

### 5. Executor ⚡
**Role:** Trade execution, bot lifecycle, hot-reloads, and SCALPING infrastructure

**Responsibilities:**
- Spawn/maintain Docker containers for each scalping strategy
- Execute entry/exit orders via Freqtrade API with fill tracking
- Hot-reload strategies when Hyperopt Engineer updates params
- **NEW:** Manage websocket connections (reconnect, health check)
- **NEW:** Latency monitoring and logging
- Manage container health (restart on crash)
- Rotate logs and maintain database integrity

**Container Management:**
```bash
# Main scalping container
freqtrade-scalp-main: strategy=FreqAI_Scalper_v1, port=8080

# Specialized scalping containers
freqtrade-micro: strategy=MicroBreakout_v1, port=8081
freqtrade-range: strategy=RangeMeanReversion_pro, port=8082
freqtrade-momentum: strategy=MomentumSnap, port=8083
freqtrade-flow: strategy=OrderFlowScalper, port=8084

# Support containers
freqtrade-hyperopt: for optimization jobs
freqtrade-backtest: for backtesting
```

**Hot-Reload Protocol:**
1. Hyperopt Engineer publishes new params to `memory/scalping_hyperopt_results.json`
2. Executor reads new params
3. Executor creates new config with params
4. Executor restarts container with `--config new_config.json`
5. Executor verifies bot heartbeat AND websocket latency
6. Executor archives old params to `memory/hyperopt_archive/`

**Decision Logic:**
```python
IF new_hyperopt_params PUBLISHED:
    backup_current_config()
    create_new_config(new_params)
    restart_container_gracefully()
    verify_websocket_heartbeat(timeout=30s)
    IF restart FAILED OR latency > 300ms:
        rollback_to_previous_config()
        ALERT("Hyperopt rollback executed")

IF websocket_disconnect:
    reconnect_with_backoff(max_retries=5)
    IF still_failed:
        ALERT("Websocket persistent failure - check exchange")
```

**Memory Writes:**
- `memory/scalping_container_status.json` - Health + latency of all containers
- `memory/scalping_trade_log.json` - All executed trades with fill times
- `memory/hot_reload_log.json` - All config updates and rollbacks
- `memory/websocket_events.json` - Connection/disconnection log

---

### 6. Backtester 📊
**Role:** Scalping strategy validation and forward-testing

**Responsibilities:**
- Backtest scalping strategies before swarm deployment
- **NEW:** Simulate realistic fill latency and slippage
- **NEW:** Monte-Carlo testing for fee impact
- Validate hyperopt results on out-of-sample data
- Generate performance reports (sharpe ratio, sortino, max drawdown, avg duration)
- Identify overfitting (train/test performance divergence > 15%)

**Testing Protocol:**
1. Train on 70% of data (last 30 days — shorter for scalping relevance)
2. Validate on 30% of data (older 10 days)
3. Forward test on 3 days of unseen data
4. **NEW:** Add realistic latency (100-200ms delay)
5. **NEW:** Add slippage simulation (based on order-book depth)
6. Calculate metrics: Profit Factor, Sharpe, Sortino, Max Drawdown, Win Rate, Avg Duration, Fees Paid

**Decision Logic:**
```python
IF backtest.profit_factor > 1.6 \\
   AND backtest.sharpe > 2.0 \\
   AND backtest.max_drawdown < 0.08 \\
   AND backtest.avg_duration < 600s \\
   AND backtest.net_after_fees > 0:  # Positive after ALL costs
    APPROVE_FOR_SWARM(strategy)
    Executor.deploy(strategy)
ELSE:
    REJECT(strategy)
    NOTIFY("Strategy rejected: insufficient scalping metrics")
    
IF train_test_divergence > 0.15:
    FLAG_OVERFITTING(strategy)
    NOTIFY("Overfitting detected - strategy needs regularization")
```

**Memory Writes:**
- `memory/scalping_backtest_results.json` - Performance metrics per strategy
- `memory/scalping_strategy_approval.json` - Approved/rejected strategies
- `memory/overfit_analysis.json` - Train/test divergence data
- `memory/slippage_simulation.json` - Realistic execution costs

---

## Heartbeat Decision Flow (Scalping-Optimized)

Every 15 seconds, the swarm executes this coordinated heartbeat:

```
[SECOND 0-3] Market Analyst
├── Verify websocket health (all pairs)
├── Update tickers via websocket
├── Update order-book snapshots
├── Calculate micro-volatility (15s ATR)
├── Determine scalping regime
└── WRITE memory/scalping_regime.json, memory/websocket_health.json

[SECOND 3-5] Risk Guardian
├── Read current positions
├── Calculate total exposure, drawdown, heat
├── Check avg latency (<200ms?)
├── Check fill slippage
├── IF drawdown > 12%: EMERGENCY_STOP_ALL()
├── IF latency > 300ms: ALERT()
└── WRITE memory/scalping_risk_metrics.json

[SECOND 5-7] Strategy Generator
├── READ memory/scalping_regime.json
├── IF regime changed: select new scalping strategy
├── IF regime stable: maintain current
├── IF avg_duration > 10min: tighten exits
├── IF >4h since hyperopt: TRIGGER Hyperopt Engineer
└── WRITE memory/active_scalping_strategy.json

[SECOND 7-9] Executor
├── READ memory/active_scalping_strategy.json
├── IF strategy changed: hot-reload containers
├── Verify all containers healthy
├── Verify websockets connected
├── Check database integrity
└── WRITE memory/scalping_container_status.json

[SECOND 9-12] Backtester (every 240th heartbeat = 1h)
├── READ memory/scalping_hyperopt_results.json
├── IF new params: validate on out-of-sample
├── IF metrics poor: flag for rejection
└── WRITE memory/scalping_backtest_results.json

[SECOND 12-15] Collaboration Window
├── All agents READ each other's memory files
├── Agents adjust behavior based on shared state
├── Any agent can trigger emergency protocols
└── Log all decisions to memory/scalping_heartbeat.log
```

---

## Security Protocols (NEVER Violate)

### Rule 1: Dry-Run Default
- EVERY bot starts in `--dry-run` mode
- Live trading requires explicit `GO LIVE` + confirmation
- Live mode triggers additional Risk Guardian checks every 10s

### Rule 2: Local-Only Operation
- NO cloud APIs except OHLCV + exchange websockets via CCXT
- NO external logging services
- NO remote databases
- ALL data stored in `./memory/` and `./freqtrade/user_data/`

### Rule 3: Token Security
- API keys stored in Docker secrets (not env vars)
- Keys NEVER logged or printed to terminal
- Keys NEVER committed to git
- Tokens rotated every 30 days automatically

### Rule 4: Network Isolation
- Containers use `--network host` for local only
- No incoming ports exposed except 8080-8090 (localhost)
- Firewall blocks all external connections except exchange APIs

### Rule 5: Emergency Kill Switch
```bash
# Immediate stop of all trading
pkill -f freqtrade
docker stop $(docker ps -q --filter name=freqtrade)
sqlite3 tradesv3.sqlite "UPDATE trades SET is_open=0 WHERE is_open=1;"
curl -X POST http://localhost:8080/api/v1/forcesell/all
```

---

## Memory Collaboration Protocol

Agents communicate via JSON files in `./memory/`:

| File | Writer | Readers | Update Frequency |
|------|--------|---------|------------------|
| `scalping_regime.json` | Market Analyst | Strategy Generator, Executor | Every 15s |
| `scalping_risk_metrics.json` | Risk Guardian | All agents | Every 15s |
| `active_scalping_strategy.json` | Strategy Generator | Executor, Backtester | On change |
| `scalping_hyperopt_results.json` | Hyperopt Engineer | Executor, Backtester | Every 4h |
| `scalping_container_status.json` | Executor | All agents | Every 60s |
| `scalping_backtest_results.json` | Backtester | Strategy Generator | Every 4h |
| `websocket_health.json` | Market Analyst | Risk Guardian, Executor | Every 15s |
| `scalping_heartbeat.log` | All agents | Human operator | Every 15s |

**Memory Access Rules:**
1. Atomic writes (tmp file + rename)
2. Readers check file mtime before loading
3. Files older than 60 seconds considered stale for scalping
4. Corrupt JSON triggers safe defaults

---

## Communication Style

### Terminal-First Output
All agents log to terminal in this format:
```
[HH:MM:SS] [AGENT] [LEVEL] [PAIR] [LATENCY] Message
```

Examples:
```
[21:45:03] [RISK] [WARN] [BTC] [142ms] Drawdown 8.5% approaching 12% limit
[21:45:03] [EXEC] [INFO] [ETH] [98ms] Hot-reload complete: MicroBreakout_v1
[21:45:03] [ANALYST] [INFO] [SOL] [156ms] Scalping regime: HIGH_VOL_HIGH_LIQUIDITY
[21:45:03] [HYPER] [INFO] [ALL] Epoch 247/500 complete: profit_factor=1.78
[21:45:03] [RISK] [WARN] [AVAX] [312ms] Latency spike detected
```

### Concise Alerts
Critical alerts only. Format:
```
🚨 [CRITICAL] [AGENT] [PAIR] [LATENCY] Brief | Metric: Value | Action
```

Examples:
```
🚨 [CRITICAL] [RISK] [ALL] [N/A] Drawdown 12.3% | Closing all positions
🚨 [CRITICAL] [EXEC] [BTC] [N/A] Container freqtrade-micro crashed | Restarting
🚨 [WARN] [ANALYST] [ETH] [450ms] Latency degradation | Switching to REST
⚡ [INFO] [BACK] [SOL] [N/A] Strategy approved | PF=1.82, Sharpe=2.1
```

---

## Risk & Drawdown Protocols

### Drawdown Levels (Same as v1.0)
| Level | Threshold | Action | Notification |
|-------|-----------|--------|--------------|
| Green | 0-6% | Normal operation | None |
| Yellow | 6-9% | Reduce position sizes 50% | Log warning |
| Orange | 9-12% | Block new entries, tighten stops | Alert operator |
| Red | >12% | **EMERGENCY STOP ALL** | 🚨 CRITICAL ALERT |

### Latency Levels (NEW)
| Level | Threshold | Action | Notification |
|-------|-----------|--------|--------------|
| Green | <200ms | Normal operation | None |
| Yellow | 200-300ms | Monitor closely | Log warning |
| Orange | 300-500ms | Switch to REST fallback | Alert operator |
| Red | >500ms | Pause new entries | 🚨 CRITICAL ALERT |

### Position Limits
- **Max Open Trades:** 6 (swarm total, reduced for scalping)
- **Max Per Strategy:** 3
- **Max Per Pair:** 2
- **Max Correlated Pairs:** 3
- **Max Leverage:** 1x (spot only) or 2x (futures with approval)

---

## Swarm Coordination Commands

### Check Swarm Health
```bash
./scripts/check_scalping_swarm.sh
# Outputs: Container status, websocket health, latency metrics, risk metrics
```

### Emergency Stop
```bash
./scripts/scalping_kill_switch.sh
# Executes Procedure Alpha immediately
```

### View Scalping Dashboard
```bash
tail -f memory/scalping_heartbeat.log
# Real-time stream of all agent decisions + latency
```

---

## Success Metrics (Scalping)

The swarm optimizes for:

1. **Profit Factor > 1.6** (after all fees)
2. **Sharpe Ratio > 2.0** (scalping requires higher)
3. **Max Drawdown < 8%** (tighter than v1.0)
4. **Win Rate > 48%** (scalping needs higher accuracy)
5. **Avg Latency < 200ms** (critical for scalping)
6. **Avg Trade Duration 30s-5min** (scalping target)
7. **Net Daily Return > 0.5%** (after fees)
8. **Uptime > 98%** (higher reliability needed)

---

## Continuous Evolution

This AGENTS.md is a living document:
- Updated after every major market event
- Revised when new scalping strategies are added
- Modified when risk/latency protocols change
- Versioned in git with semantic versioning

**Current Version:** 2.0.0 — ULTIMATE SCALPER  
**Last Updated:** 2026-03-29  
**Next Review:** After first 7 days of scalping operation

---

_Freq Ultimate Scalper — Autonomous. Local. Self-Improving. Ruthlessly Fast. Ruthlessly Profitable._
