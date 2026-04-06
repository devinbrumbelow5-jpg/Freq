#!/usr/bin/env python3
"""
Multi-Strategy Orchestrator
Manages multiple trading strategies based on market regime
Rotates strategies: Grid, Mean Reversion, Breakout Momentum
"""

import json
import os
import sys
import requests
from datetime import datetime, timedelta
import sqlite3

CONFIG_PATH = "/root/.openclaw/workspace/memory/regime_config.json"
DB_PATH = "/root/.openclaw/workspace/freqtrade/user_data/trades_multi.sqlite"
API_URL = "http://localhost:8082/api/v1"
API_AUTH = ("freq", "scalp2026")

class StrategyOrchestrator:
    def __init__(self):
        self.strategies = {
            "GridScalper_v1": {
                "regime": "LOW_VOL_TIGHT_SPREAD",
                "allocation": 0.4,
                "timeframe": "5m"
            },
            "MeanReversionScalper_v1": {
                "regime": "CHOPPY_ILLIQUID",
                "allocation": 0.35,
                "timeframe": "5m"
            },
            "BreakoutMomentum_v1": {
                "regime": "HIGH_VOL_HIGH_LIQUIDITY",
                "allocation": 0.25,
                "timeframe": "5m"
            }
        }
        self.current_regime = self._detect_regime()
        
    def _detect_regime(self) -> str:
        """Detect current market regime"""
        try:
            # Check recent volatility
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get recent trades for volatility calculation
            cursor.execute("""
                SELECT pair, close_profit, close_date 
                FROM trades 
                WHERE close_date > datetime('now', '-4 hours')
            """)
            trades = cursor.fetchall()
            conn.close()
            
            if len(trades) < 3:
                return "LOW_VOL_TIGHT_SPREAD"
            
            # Calculate volatility
            profits = [t[1] for t in trades if t[1] is not None]
            if not profits:
                return "CHOPPY_ILLIQUID"
            
            volatility = sum(abs(p) for p in profits) / len(profits)
            
            # Regime detection logic
            if volatility > 0.02:
                return "HIGH_VOL_HIGH_LIQUIDITY"
            elif volatility < 0.005:
                return "LOW_VOL_TIGHT_SPREAD"
            else:
                return "CHOPPY_ILLIQUID"
                
        except Exception as e:
            print(f"Regime detection error: {e}")
            return "CHOPPY_ILLIQUID"
    
    def get_active_strategies(self) -> list:
        """Get strategies for current regime"""
        active = []
        for name, config in self.strategies.items():
            if config["regime"] == self.current_regime:
                active.append({
                    "name": name,
                    "allocation": config["allocation"]
                })
        
        # Fallback: if no exact match, use Mean Reversion
        if not active:
            active = [{"name": "MeanReversionScalper_v1", "allocation": 1.0}]
        
        return active
    
    def rotate_strategies(self):
        """Rotate strategies based on regime"""
        new_regime = self._detect_regime()
        
        if new_regime != self.current_regime:
            print(f"[{datetime.now()}] Regime change: {self.current_regime} -> {new_regime}")
            self.current_regime = new_regime
            
            # Save config
            config = {
                "timestamp": datetime.now().isoformat(),
                "regime": self.current_regime,
                "strategies": self.get_active_strategies()
            }
            
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        return False
    
    def log_status(self):
        """Log current status"""
        print(f"[{datetime.now()}] Regime: {self.current_regime}")
        for s in self.get_active_strategies():
            print(f"  - {s['name']}: {s['allocation']*100:.0f}% allocation")

if __name__ == "__main__":
    orch = StrategyOrchestrator()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rotate":
        rotated = orch.rotate_strategies()
        print(f"Rotation {'executed' if rotated else 'not needed'}")
    else:
        orch.log_status()