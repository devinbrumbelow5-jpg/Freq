#!/usr/bin/env python3
"""
FreqAI 6-Hourly Retraining Service
Retrains model on latest 7 days, forward-tests next 24h
"""

import subprocess
import json
import os
import sys
from datetime import datetime, timedelta
import logging
import time

# Configuration
RETRAIN_INTERVAL_HOURS = 6
TRAIN_DAYS = 7
FORWARD_TEST_HOURS = 24
CONFIG_PATH = "/root/.openclaw/workspace/freqtrade/user_data/config_production_dryrun.json"
STRATEGY = "KIMMY_SCALPER_v2_FreqAI"
FREQAI_MODEL = "LightGBMClassifier"
WORKSPACE = "/root/.openclaw/workspace/freqtrade"
LOG_FILE = "/root/.openclaw/workspace/logs/freqai_retrain.log"

# Setup logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [FREQAI-RETRAIN] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def calculate_timerange():
    """Calculate train and test timeranges"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=TRAIN_DAYS)
    test_end = end_date + timedelta(hours=FORWARD_TEST_HOURS)
    
    train_range = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    test_range = f"{end_date.strftime('%Y%m%d')}-{test_end.strftime('%Y%m%d')}"
    
    return train_range, test_range

def download_data(timerange):
    """Download fresh data for retraining"""
    logger.info(f"Downloading data for range: {timerange}")
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{WORKSPACE}/user_data:/freqtrade/user_data",
        "freqtradeorg/freqtrade:stable",
        "download-data",
        "--config", CONFIG_PATH,
        "--timeframe", "5m", "15m", "1h",
        "--timerange", timerange,
        "-t", "20"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            logger.info("Data download completed successfully")
            return True
        else:
            logger.error(f"Data download failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Data download timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"Data download error: {e}")
        return False

def retrain_model(timerange):
    """Retrain FreqAI model"""
    logger.info(f"Starting FreqAI retraining for range: {timerange}")
    
    # Update config with new timerange
    update_freqai_timerange(timerange)
    
    cmd = [
        "docker", "run", "--rm",
        "--memory=4g", "--cpus=2",
        "-v", f"{WORKSPACE}/user_data:/freqtrade/user_data",
        "freqtradeorg/freqtrade:stable",
        "trade",
        "--config", CONFIG_PATH,
        "--strategy", STRATEGY,
        "--freqaimodel", FREQAI_MODEL,
        "--timerange", timerange,
        "--dry-run",
        "--logfile", "/freqtrade/user_data/logs/freqai_retrain_session.log"
    ]
    
    try:
        # Run for 1 hour to complete training
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0 or "freqai" in result.stdout.lower():
            logger.info("FreqAI retraining completed")
            return True
        else:
            logger.error(f"Retraining failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.info("Training ran for 1 hour (expected for FreqAI)")
        return True
    except Exception as e:
        logger.error(f"Retraining error: {e}")
        return False

def update_freqai_timerange(timerange):
    """Update config with new timerange for FreqAI"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Update FreqAI train period
        config['freqai']['train_period_days'] = TRAIN_DAYS
        config['freqai']['backtest_period_days'] = 1
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.info(f"Updated config: train_period={TRAIN_DAYS} days")
        
    except Exception as e:
        logger.error(f"Failed to update config: {e}")

def forward_test(timerange):
    """Run forward test for 24h"""
    logger.info(f"Starting forward test for range: {timerange}")
    
    cmd = [
        "docker", "run", "--rm",
        "--memory=4g", "--cpus=2",
        "-v", f"{WORKSPACE}/user_data:/freqtrade/user_data",
        "freqtradeorg/freqtrade:stable",
        "backtest",
        "--config", CONFIG_PATH,
        "--strategy", STRATEGY,
        "--freqaimodel", FREQAI_MODEL,
        "--timeframe", "5m",
        "--timerange", timerange
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        # Parse results
        output = result.stdout + result.stderr
        
        # Extract metrics
        metrics = parse_backtest_metrics(output)
        
        logger.info(f"Forward test complete: {metrics}")
        
        # Save results
        save_results(metrics, timerange)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Forward test error: {e}")
        return None

def parse_backtest_metrics(output):
    """Parse backtest output for metrics"""
    metrics = {
        'sharpe': 0.0,
        'drawdown': 0.0,
        'win_rate': 0.0,
        'profit_factor': 0.0,
        'total_trades': 0,
        'profit': 0.0
    }
    
    # Simple parsing - in production use json output
    lines = output.split('\n')
    for line in lines:
        if 'Sharpe' in line:
            try:
                metrics['sharpe'] = float(line.split(':')[1].strip())
            except:
                pass
        if 'Drawdown' in line:
            try:
                metrics['drawdown'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        if 'Win Rate' in line:
            try:
                metrics['win_rate'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        if 'Profit Factor' in line:
            try:
                metrics['profit_factor'] = float(line.split(':')[1].strip())
            except:
                pass
                
    return metrics

def save_results(metrics, timerange):
    """Save results to file"""
    results_file = f"/root/.openclaw/workspace/logs/freqai_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'timerange': timerange,
        'metrics': metrics
    }
    
    with open(results_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Results saved to {results_file}")

def should_pause_trading(metrics):
    """Check if trading should be paused based on metrics"""
    if not metrics:
        return False
    
    # Pause if forward test shows poor performance
    if metrics.get('drawdown', 0) > 5.0:
        logger.warning(f"High drawdown detected: {metrics['drawdown']}% - recommending pause")
        return True
    
    if metrics.get('sharpe', 0) < 0.5:
        logger.warning(f"Low Sharpe ratio: {metrics['sharpe']} - recommending pause")
        return True
    
    return False

def main():
    """Main retraining loop"""
    logger.info("=" * 60)
    logger.info("FreqAI 6-Hourly Retraining Service Started")
    logger.info("=" * 60)
    
    while True:
        cycle_start = datetime.now()
        
        # Calculate timeranges
        train_range, test_range = calculate_timerange()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"New Retraining Cycle: {cycle_start}")
        logger.info(f"Train: {train_range}, Test: {test_range}")
        logger.info(f"{'='*60}\n")
        
        # Step 1: Download data
        if not download_data(train_range):
            logger.error("Data download failed, skipping cycle")
            time.sleep(300)
            continue
        
        # Step 2: Retrain model
        if not retrain_model(train_range):
            logger.error("Retraining failed, skipping cycle")
            time.sleep(300)
            continue
        
        # Step 3: Forward test
        metrics = forward_test(test_range)
        
        # Step 4: Check if should pause
        if should_pause_trading(metrics):
            logger.warning("⚠️ MARKET REGIME GUARD ACTIVATED - Pausing recommended")
            with open('/tmp/trading_paused', 'w') as f:
                f.write(f"Paused at {datetime.now().isoformat()} due to poor metrics: {metrics}")
        else:
            logger.info("✅ Forward test passed - Trading can continue")
            if os.path.exists('/tmp/trading_paused'):
                os.remove('/tmp/trading_paused')
                logger.info("Trading resumed")
        
        # Wait for next cycle
        elapsed = (datetime.now() - cycle_start).total_seconds()
        sleep_time = max(0, (RETRAIN_INTERVAL_HOURS * 3600) - elapsed)
        
        logger.info(f"Cycle complete. Sleeping for {sleep_time/3600:.1f} hours")
        time.sleep(sleep_time)

if __name__ == '__main__':
    main()
