# FreqAI 6-Hourly Retraining + Regime Guard - DEPLOYED

**Timestamp:** 2026-04-02  
**Status:** ✅ FULLY DEPLOYED

---

## 🎯 IMPLEMENTED FEATURES

### 1. ✅ 6-Hourly FreqAI Retraining
- **Script:** `scripts/freqai_retrain_service.py`
- **Schedule:** Every 6 hours (cron)
- **Training Data:** Latest 7 days
- **Forward Test:** Next 24 hours
- **Actions:**
  - Downloads fresh data
  - Retrains LightGBM model
  - Runs forward backtest
  - Evaluates metrics
  - Auto-pauses if performance poor

### 2. ✅ Market Regime Guard (Drawdown >5%)
- **Script:** `scripts/drawdown_regime_guard.py`
- **Monitor:** Every minute (cron)
- **Trigger:** Drawdown >5% in last 4 hours
- **Actions:**
  - Monitors closed trades
  - Tracks open positions
  - Pauses trading via `/tmp/trading_paused`
  - Auto-resumes when conditions normalize
  - Sends alerts

### 3. ✅ Cron Automation
- **File:** `config/freqai_crontab`
- **Jobs:**
  - FreqAI retrain: Every 6 hours
  - Drawdown guard: Every minute
  - Performance report: Every hour
  - Log rotation: Daily 2 AM
  - Health monitor: Every 5 minutes
  - DB backup: Daily 4 AM

### 4. ✅ 7-Day Forward Simulation
- **Script:** `scripts/forward_simulation.py`
- **Purpose:** Test strategy over 7 days
- **Output:** Equity curve, trade log, metrics
- **Target:** Confirm consistent profitability

---

## 📊 RUNNING SERVICES

| Service | Status | Schedule |
|---------|--------|----------|
| Drawdown Regime Guard | 🟢 Running | Every minute |
| FreqAI Retrain | ⏰ Scheduled | Every 6 hours |
| Health Monitor | ⏰ Scheduled | Every 5 minutes |

---

## 🚨 REGIME GUARD STATES

### Trading Paused When:
- Drawdown > 5% in last 4 hours
- Sharpe ratio < 0.5 in forward test
- Multiple consecutive losses

### Trading Resumes When:
- Drawdown recovers below 3%
- Next retraining cycle shows positive metrics
- Manual resume via `rm /tmp/trading_paused`

---

## 📈 MONITORING

### Check Status
```bash
# View regime guard log
tail -f /root/.openclaw/workspace/logs/regime_guard.log

# Check if trading paused
cat /tmp/trading_paused 2>/dev/null || echo "Trading active"

# View recent trades
./scripts/performance_report.sh
```

### Alerts
- Console logs
- `/root/.openclaw/workspace/logs/alerts.log`
- WhatsApp-compatible format

---

## 🔄 RETRAINING WORKFLOW

```
Every 6 hours:
  ↓
Download latest 7 days data
  ↓
Retrain LightGBM model (FreqAI)
  ↓
Forward test next 24 hours
  ↓
Evaluate metrics:
  - Sharpe > 0.5?
  - Drawdown < 5%?
  - Win rate > 50%?
  ↓
IF metrics good → Continue trading
IF metrics poor  → Pause trading
  ↓
Wait 6 hours → Repeat
```

---

## 🧪 7-DAY SIMULATION

### Run Manually
```bash
python3 /root/.openclaw/workspace/scripts/forward_simulation.py
```

### Expected Output
- Total profit %
- Average Sharpe ratio
- Max drawdown
- Profitable cycle count
- Win rate
- Equity curve JSON

### Success Criteria
- Total profit > 0%
- Win rate > 50%
- Max drawdown < 10%

---

## 📁 FILES CREATED

```
scripts/
├── freqai_retrain_service.py      # Main retraining service
├── drawdown_regime_guard.py        # Drawdown monitoring
└── forward_simulation.py           # 7-day test

config/
└── freqai_crontab                  # Automation schedule

logs/
├── regime_guard.log                # Guard activity
├── freqai_retrain.log              # Retraining sessions
├── freqai_retrain_cron.log         # Cron retraining
└── simulation_results.json         # 7-day results
```

---

## 🎯 NEXT STEPS

1. **Monitor first 24h:** Check regime guard is working
2. **First retrain:** At next 6-hour mark (00:00, 06:00, 12:00, 18:00)
3. **Review metrics:** Check forward test results
4. **Run simulation:** Execute 7-day forward test
5. **Verify profitability:** Confirm consistent performance

---

## ⚠️ IMPORTANT NOTES

1. **Dry-Run Mode:** All trading is simulated (no real funds)
2. **Exchange:** OKX (Binance geo-blocked)
3. **Strategy:** KIMMY_SCALPER_v2_FreqAI
4. **Data:** 7-day rolling window, 5m timeframe
5. **Auto-Recovery:** System self-heals on crashes

---

## 📊 CURRENT STATUS

**Drawdown Guard:** 🟢 Active (PID monitoring)
**Retraining:** ⏰ Scheduled (next: 6-hour mark)
**Simulation:** 📋 Ready to run
**Trading:** ✅ Enabled (until drawdown >5%)

---

**Automation Complete. System is self-managing with 6-hourly retraining and drawdown protection.**
