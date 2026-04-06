#!/usr/bin/env python3
"""
Smart Position Sizing Module
Kelly Criterion + Volatility Adjustment + Portfolio Heat
"""

import math
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

DB_PATH = "/root/.openclaw/workspace/freqtrade/user_data/trades_multi.sqlite"
CONFIG_PATH = "/root/.openclaw/workspace/memory/position_sizing_config.json"

class SmartPositionSizer:
    """
    Calculates optimal position size using:
    - Kelly Criterion (win rate, avg win/loss ratio)
    - Volatility adjustment (ATR-based)
    - Portfolio heat management
    - Strategy-specific multipliers
    """
    
    def __init__(self, base_capital: float = 500.0):
        self.base_capital = base_capital
        self.max_position_pct = 0.15  # Max 15% of capital per trade
        self.min_position_pct = 0.03   # Min 3% of capital per trade
        self.load_config()
        
    def load_config(self):
        """Load or create config"""
        try:
            with open(CONFIG_PATH, 'r') as f:
                self.config = json.load(f)
        except:
            self.config = {
                "kelly_fraction": 0.3,  # Use 30% of Kelly (conservative)
                "volatility_lookback": 20,
                "strategy_multipliers": {
                    "MeanReversionScalper_v1": 1.0,
                    "GridScalper_v1": 1.2,
                    "BreakoutMomentum_v1": 0.8
                }
            }
            self.save_config()
    
    def save_config(self):
        """Save config to disk"""
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def calculate_kelly(self, strategy: str = "default") -> float:
        """Calculate Kelly Criterion for position sizing"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get recent trades for this strategy
            cursor.execute("""
                SELECT close_profit 
                FROM trades 
                WHERE is_open = 0 
                AND strategy = ?
                AND close_date > datetime('now', '-7 days')
            """, (strategy,))
            
            profits = [row[0] for row in cursor.fetchall() if row[0] is not None]
            conn.close()
            
            if len(profits) < 5:
                return 0.05  # Default 5% if insufficient data
            
            # Calculate win rate
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            
            if not wins or not losses:
                return 0.05
            
            win_rate = len(wins) / len(profits)
            avg_win = sum(wins) / len(wins)
            avg_loss = abs(sum(losses) / len(losses))
            
            # Kelly formula: (bp - q) / b
            # where b = avg win / avg loss, p = win rate, q = 1 - p
            b = avg_win / avg_loss if avg_loss > 0 else 1
            p = win_rate
            q = 1 - p
            
            kelly = (b * p - q) / b if b > 0 else 0
            kelly = max(0, min(kelly, 0.5))  # Cap at 50%
            
            # Apply fractional Kelly (conservative)
            return kelly * self.config["kelly_fraction"]
            
        except Exception as e:
            print(f"Kelly calculation error: {e}")
            return 0.05
    
    def calculate_volatility_factor(self, atr_pct: float) -> float:
        """Adjust position size based on volatility"""
        # Lower position size when volatility is high
        if atr_pct > 3.0:
            return 0.5  # High vol = half size
        elif atr_pct > 2.0:
            return 0.75
        elif atr_pct > 1.0:
            return 1.0
        else:
            return 1.2  # Low vol = increase size
    
    def calculate_heat_factor(self, current_heat: float) -> float:
        """Reduce size as portfolio heat increases"""
        max_heat = 0.06  # 6% max
        
        if current_heat > max_heat:
            return 0.0  # No new positions
        elif current_heat > max_heat * 0.8:
            return 0.5
        elif current_heat > max_heat * 0.5:
            return 0.75
        else:
            return 1.0
    
    def get_position_size(self, strategy: str, atr_pct: float = 1.5, 
                          current_heat: float = 0.0) -> Tuple[float, Dict]:
        """
        Calculate optimal position size
        Returns: (size_usdt, calculation_details)
        """
        # Base Kelly sizing
        kelly_pct = self.calculate_kelly(strategy)
        
        # Volatility adjustment
        vol_factor = self.calculate_volatility_factor(atr_pct)
        
        # Heat adjustment
        heat_factor = self.calculate_heat_factor(current_heat)
        
        # Strategy multiplier
        strat_mult = self.config["strategy_multipliers"].get(strategy, 1.0)
        
        # Calculate final position percentage
        position_pct = kelly_pct * vol_factor * heat_factor * strat_mult
        
        # Apply limits
        position_pct = max(self.min_position_pct, min(position_pct, self.max_position_pct))
        
        # Calculate actual size
        position_size = self.base_capital * position_pct
        
        details = {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy,
            "base_capital": self.base_capital,
            "kelly_pct": kelly_pct,
            "volatility_factor": vol_factor,
            "heat_factor": heat_factor,
            "strategy_multiplier": strat_mult,
            "final_position_pct": position_pct,
            "position_size_usdt": position_size,
            "atr_pct": atr_pct,
            "current_heat": current_heat
        }
        
        return position_size, details
    
    def log_calculation(self, details: Dict):
        """Log position sizing calculation"""
        log_file = "/root/.openclaw/workspace/logs/position_sizing.log"
        with open(log_file, 'a') as f:
            f.write(f"[{details['timestamp']}] {details['strategy']}: "
                   f"${details['position_size_usdt']:.2f} "
                   f"({details['final_position_pct']*100:.1f}%) "
                   f"| Kelly: {details['kelly_pct']*100:.1f}% "
                   f"| Vol: {details['volatility_factor']:.2f}x "
                   f"| Heat: {details['heat_factor']:.2f}x\n")

if __name__ == "__main__":
    sizer = SmartPositionSizer()
    
    # Test calculations for each strategy
    for strategy in ["MeanReversionScalper_v1", "GridScalper_v1", "BreakoutMomentum_v1"]:
        size, details = sizer.get_position_size(strategy, atr_pct=1.5, current_heat=0.02)
        sizer.log_calculation(details)
        print(f"{strategy}: ${size:.2f} USDT ({details['final_position_pct']*100:.1f}%)")