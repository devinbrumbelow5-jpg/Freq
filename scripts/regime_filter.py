#!/usr/bin/env python3
"""
Freq Regime Filter Service
Production 2026 - Pauses trading when market conditions are unfavorable

Triggers:
- 1h volatility > 3%
- BTC dominance spike > threshold
- Exchange API unresponsive

Actions:
- Pause trading via freqtrade API
- Send alerts
- Resume when conditions normalize
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Configuration from environment
VOLATILITY_THRESHOLD = float(os.getenv('VOLATILITY_THRESHOLD', 0.03))
BTC_DOMINANCE_THRESHOLD = float(os.getenv('BTC_DOMINANCE_THRESHOLD', 0.60))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 300))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
FREQTRADE_API = "http://freqtrade-range:8080/api/v1"
API_AUTH = ("freq", "scalp2026")

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [REGIME-FILTER] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/logs/regime_filter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Data sources
EXCHANGE_APIS = {
    'binance': {
        'klines': 'https://api.binance.com/api/v3/klines',
        'ticker': 'https://api.binance.com/api/v3/ticker/24hr'
    },
    'okx': {
        'klines': 'https://www.okx.com/api/v5/market/history-candles',
        'ticker': 'https://www.okx.com/api/v5/market/tickers'
    },
    'coingecko': {
        'dominance': 'https://api.coingecko.com/api/v3/global'
    }
}


class RegimeFilter:
    """Market regime detection and trading control"""
    
    def __init__(self):
        self.is_trading_paused = False
        self.pause_reason = None
        self.pause_start_time = None
        self.last_check = None
        self.consecutive_warnings = 0
        self.max_warnings = 3
        
    def log_status(self, message: str, level: str = 'info'):
        """Log with appropriate level"""
        getattr(logger, level.lower(), logger.info)(message)
    
    def get_btc_volatility(self, exchange: str = 'okx') -> Optional[float]:
        """Calculate BTC 1h volatility (ATR-based)"""
        try:
            if exchange == 'okx':
                # Get 24 candles (1h timeframe)
                url = f"{EXCHANGE_APIS['okx']['klines']}?instId=BTC-USDT&bar=1H&limit=25"
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if data.get('code') != '0':
                    return None
                
                candles = data['data']
                if len(candles) < 2:
                    return None
                
                # Calculate returns
                returns = []
                for i in range(1, len(candles)):
                    prev_close = float(candles[i][4])
                    curr_close = float(candles[i-1][4])
                    returns.append(abs(curr_close - prev_close) / prev_close)
                
                # Return mean volatility
                return sum(returns) / len(returns)
                
            elif exchange == 'binance':
                url = f"{EXCHANGE_APIS['binance']['klines']}?symbol=BTCUSDT&interval=1h&limit=25"
                response = requests.get(url, timeout=10)
                candles = response.json()
                
                if not candles or len(candles) < 2:
                    return None
                
                returns = []
                for i in range(1, len(candles)):
                    prev_close = float(candles[i-1][4])
                    curr_close = float(candles[i][4])
                    returns.append(abs(curr_close - prev_close) / prev_close)
                
                return sum(returns) / len(returns)
                
        except Exception as e:
            self.log_status(f"Error fetching BTC volatility: {e}", 'error')
            return None
    
    def get_btc_dominance(self) -> Optional[float]:
        """Get BTC market dominance from CoinGecko"""
        try:
            url = EXCHANGE_APIS['coingecko']['dominance']
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'data' in data and 'market_cap_percentage' in data['data']:
                btc_dominance = data['data']['market_cap_percentage'].get('btc', 0) / 100
                return btc_dominance
            return None
            
        except Exception as e:
            self.log_status(f"Error fetching BTC dominance: {e}", 'error')
            return None
    
    def check_exchange_health(self) -> Dict[str, bool]:
        """Check if exchanges are responsive"""
        health = {}
        
        for exchange, urls in EXCHANGE_APIS.items():
            if exchange == 'coingecko':
                continue
            try:
                response = requests.get(urls['ticker'], timeout=5)
                health[exchange] = response.status_code == 200
            except:
                health[exchange] = False
        
        return health
    
    def pause_trading(self, reason: str):
        """Pause trading via freqtrade API"""
        if self.is_trading_paused:
            return
        
        try:
            # Try to stop trading
            response = requests.post(
                f"{FREQTRADE_API}/stop",
                auth=API_AUTH,
                timeout=5
            )
            
            self.is_trading_paused = True
            self.pause_reason = reason
            self.pause_start_time = datetime.now()
            
            self.log_status(f"🛑 TRADING PAUSED: {reason}", 'warning')
            
            # Log to profits directory for alerts
            with open('/profits/alerts.txt', 'a') as f:
                f.write(f"[{datetime.now().isoformat()}] TRADING PAUSED: {reason}\n")
                
        except Exception as e:
            self.log_status(f"Failed to pause trading: {e}", 'error')
    
    def resume_trading(self):
        """Resume trading via freqtrade API"""
        if not self.is_trading_paused:
            return
        
        try:
            response = requests.post(
                f"{FREQTRADE_API}/start",
                auth=API_AUTH,
                timeout=5
            )
            
            duration = datetime.now() - self.pause_start_time if self.pause_start_time else timedelta(0)
            
            self.is_trading_paused = False
            self.pause_reason = None
            self.pause_start_time = None
            self.consecutive_warnings = 0
            
            self.log_status(f"✅ TRADING RESUMED (paused for {duration.seconds}s)", 'info')
            
            # Log to profits directory
            with open('/profits/alerts.txt', 'a') as f:
                f.write(f"[{datetime.now().isoformat()}] TRADING RESUMED after {duration.seconds}s\n")
                
        except Exception as e:
            self.log_status(f"Failed to resume trading: {e}", 'error')
    
    def check_market_conditions(self) -> Dict[str, Any]:
        """Check all market conditions"""
        conditions = {
            'volatile': False,
            'btc_spike': False,
            'unhealthy_exchanges': [],
            'details': {}
        }
        
        # Check BTC volatility
        volatility = self.get_btc_volatility()
        if volatility is not None:
            conditions['details']['btc_volatility'] = f"{volatility:.4f}"
            if volatility > VOLATILITY_THRESHOLD:
                conditions['volatile'] = True
                conditions['details']['volatility_alert'] = f"{volatility:.2%} > {VOLATILITY_THRESHOLD:.2%}"
        
        # Check BTC dominance
        dominance = self.get_btc_dominance()
        if dominance is not None:
            conditions['details']['btc_dominance'] = f"{dominance:.2%}"
            if dominance > BTC_DOMINANCE_THRESHOLD:
                conditions['btc_spike'] = True
                conditions['details']['dominance_alert'] = f"{dominance:.2%} > {BTC_DOMINANCE_THRESHOLD:.2%}"
        
        # Check exchange health
        exchange_health = self.check_exchange_health()
        conditions['details']['exchange_health'] = exchange_health
        conditions['unhealthy_exchanges'] = [e for e, h in exchange_health.items() if not h]
        
        return conditions
    
    def run(self):
        """Main loop"""
        self.log_status("Regime Filter Service Started")
        self.log_status(f"Volatility threshold: {VOLATILITY_THRESHOLD:.2%}")
        self.log_status(f"BTC dominance threshold: {BTC_DOMINANCE_THRESHOLD:.2%}")
        self.log_status(f"Check interval: {CHECK_INTERVAL}s")
        
        # Write PID file
        with open('/tmp/regime-filter.pid', 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            while True:
                self.last_check = datetime.now()
                
                # Check market conditions
                conditions = self.check_market_conditions()
                
                # Determine if we should pause
                should_pause = (
                    conditions['volatile'] or 
                    conditions['btc_spike'] or
                    len(conditions['unhealthy_exchanges']) >= 2
                )
                
                if should_pause:
                    self.consecutive_warnings += 1
                    
                    if self.consecutive_warnings >= self.max_warnings:
                        reasons = []
                        if conditions['volatile']:
                            reasons.append(f"High volatility ({conditions['details'].get('volatility_alert', '')})")
                        if conditions['btc_spike']:
                            reasons.append(f"BTC dominance spike ({conditions['details'].get('dominance_alert', '')})")
                        if conditions['unhealthy_exchanges']:
                            reasons.append(f"Unhealthy exchanges: {', '.join(conditions['unhealthy_exchanges'])}")
                        
                        reason = "; ".join(reasons)
                        self.pause_trading(reason)
                else:
                    # Conditions normal
                    if self.is_trading_paused:
                        self.resume_trading()
                    self.consecutive_warnings = 0
                
                # Log status
                status = "PAUSED" if self.is_trading_paused else "ACTIVE"
                self.log_status(
                    f"Status: {status} | Vol: {conditions['details'].get('btc_volatility', 'N/A')} "
                    f"| Dom: {conditions['details'].get('btc_dominance', 'N/A')} "
                    f"| Exchanges: {conditions['details'].get('exchange_health', {})}",
                    'info' if not self.is_trading_paused else 'warning'
                )
                
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            self.log_status("Shutting down gracefully...", 'info')
            if self.is_trading_paused:
                self.resume_trading()
        finally:
            os.remove('/tmp/regime-filter.pid')


if __name__ == '__main__':
    filter_service = RegimeFilter()
    filter_service.run()
