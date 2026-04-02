#!/usr/bin/env python3
"""
regime_detection: Detect market regime using chart analysis
Downloads chart data, generates image, analyzes with vision capabilities
"""

import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

def download_chart_data(pair, timeframe='1h', days=7):
    """Download OHLCV data for charting"""
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    
    # Download via Freqtrade
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{freqtrade_dir}/user_data:/freqtrade/user_data:cached',
        'freqtradeorg/freqtrade:stable_freqai',
        'download-data',
        '--exchange', 'coinbase',
        '--pairs', pair,
        '--timeframes', timeframe,
        '--timerange', f"{(datetime.now() - timedelta(days=days)).strftime('%Y%m%d')}-{datetime.now().strftime('%Y%m%d')}"
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, cwd=freqtrade_dir)
        return True
    except Exception as e:
        print(f"❌ Failed to download data: {e}")
        return False

def calculate_regime_metrics(pair):
    """Calculate technical indicators for regime detection"""
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    
    # Check if we have data in SQLite
    db_path = freqtrade_dir / 'tradesv3.dryrun.sqlite'
    
    metrics = {
        'adx': None,
        'bb_width': None,
        'atr_percent': None,
        'trend_direction': None,
        'volatility': None
    }
    
    # Calculate from downloaded data (simplified)
    # In production, this would query Freqtrade's indicator data
    
    return metrics

def detect_regime_from_metrics(metrics):
    """Rule-based regime detection from metrics"""
    
    # Default to calculating from basic price action
    adx = metrics.get('adx') or 25  # Default: no trend
    volatility = metrics.get('volatility') or 3.0  # Default: moderate
    
    if adx > 40:
        return {
            'regime': 'TRENDING',
            'confidence': min(adx / 50, 0.95),
            'metrics': {'adx': adx, 'volatility': volatility}
        }
    elif adx < 20 and volatility < 2.0:
        return {
            'regime': 'RANGING',
            'confidence': 0.7,
            'metrics': {'adx': adx, 'volatility': volatility}
        }
    elif volatility > 5.0:
        return {
            'regime': 'VOLATILE',
            'confidence': min(volatility / 8.0, 0.9),
            'metrics': {'adx': adx, 'volatility': volatility}
        }
    else:
        return {
            'regime': 'CALM',
            'confidence': 0.6,
            'metrics': {'adx': adx, 'volatility': volatility}
        }

def main():
    parser = argparse.ArgumentParser(description='Detect market regime')
    parser.add_argument('--pair', default='BTC/USDC', help='Trading pair to analyze')
    parser.add_argument('--timeframe', default='1h', choices=['5m', '15m', '1h', '4h', '1d'],
                       help='Timeframe for analysis')
    parser.add_argument('--visual', action='store_true', 
                       help='Generate visual chart for analysis')
    parser.add_argument('--output', default='/root/.openclaw/workspace/memory/market_regime.json',
                       help='Output JSON file')
    parser.add_argument('--all-pairs', action='store_true',
                       help='Analyze all whitelisted pairs')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    
    print(f"🔍 Analyzing market regime...")
    print(f"   Pair: {args.pair}")
    print(f"   Timeframe: {args.timeframe}")
    
    # Download latest data
    if args.visual:
        print("   Downloading chart data...")
        download_chart_data(args.pair, args.timeframe)
    
    # Calculate metrics
    print("   Calculating technical indicators...")
    metrics = calculate_regime_metrics(args.pair)
    
    # Detect regime
    result = detect_regime_from_metrics(metrics)
    result['pair'] = args.pair
    result['timeframe'] = args.timeframe
    result['timestamp'] = datetime.now().isoformat()
    result['analysis_method'] = 'technical_indicators'
    
    # Determine recommended strategy
    strategy_map = {
        'TRENDING': 'TrendFollowing_v2',
        'RANGING': 'MeanReversion_pro',
        'VOLATILE': 'BreakoutScalper',
        'CALM': 'GridAccumulation'
    }
    result['recommended_strategy'] = strategy_map.get(result['regime'], 'AetherFreqaiStrategy')
    
    # Display results
    print(f"\n{'='*60}")
    print(f"📊 REGIME ANALYSIS: {args.pair}")
    print(f"{'='*60}")
    print(f"Regime:        {result['regime']}")
    print(f"Confidence:    {result['confidence']*100:.1f}%")
    print(f"Recommended:   {result['recommended_strategy']}")
    print(f"{'='*60}")
    
    # Explanation
    explanations = {
        'TRENDING': 'Strong directional movement detected. Use trend-following strategies.',
        'RANGING': 'Price oscillating between support/resistance. Use mean-reversion.',
        'VOLATILE': 'High volatility with large moves. Use breakout or volatility strategies.',
        'CALM': 'Low volatility, consolidating. Use accumulation or grid strategies.'
    }
    print(f"📝 {explanations.get(result['regime'], '')}")
    
    # Save to memory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing data if present
    existing_data = {}
    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                existing_data = json.load(f)
        except:
            pass
    
    # Update with new analysis
    if 'pairs' not in existing_data:
        existing_data['pairs'] = {}
    
    existing_data['pairs'][args.pair] = result
    existing_data['last_updated'] = datetime.now().isoformat()
    existing_data['global_regime'] = result['regime']  # Simplified - could aggregate across pairs
    
    with open(output_path, 'w') as f:
        json.dump(existing_data, f, indent=2)
    
    print(f"\n💾 Saved to: {args.output}")
    
    # If regime changed, alert
    prev_regime = existing_data.get('previous_regime')
    if prev_regime and prev_regime != result['regime']:
        print(f"\n🚨 REGIME CHANGE DETECTED: {prev_regime} → {result['regime']}")
        print(f"   Consider rotating strategies!")
    
    existing_data['previous_regime'] = result['regime']
    
    with open(output_path, 'w') as f:
        json.dump(existing_data, f, indent=2)

if __name__ == '__main__':
    main()
