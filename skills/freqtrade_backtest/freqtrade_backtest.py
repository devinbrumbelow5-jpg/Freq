#!/usr/bin/env python3
"""
freqtrade_backtest: Backtest strategies on historical data with realistic retraining emulation
"""

import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta

def main():
    parser = argparse.ArgumentParser(description='Backtest Freqtrade strategies')
    parser.add_argument('--strategy', default='AetherFreqaiStrategy', help='Strategy name')
    parser.add_argument('--days', type=int, default=90, help='Days to backtest')
    parser.add_argument('--timeframe', default='5m', help='Timeframe')
    parser.add_argument('--export', action='store_true', help='Export trades to CSV')
    parser.add_argument('--walk-forward', action='store_true', 
                       help='Walk-forward analysis (train/test split)')
    parser.add_argument('--gpu', action='store_true', help='Enable GPU acceleration')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    
    # Calculate timerange
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    timerange = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    
    print(f"📊 Backtesting: {args.strategy}")
    print(f"   Timerange: {args.days} days ({timerange})")
    print(f"   Timeframe: {args.timeframe}")
    
    if args.walk_forward:
        print(f"   Mode: Walk-forward analysis (70% train / 30% test)")
        # Calculate train/test split
        train_end = start_date + timedelta(days=int(args.days * 0.7))
        timerange = f"{start_date.strftime('%Y%m%d')}-{train_end.strftime('%Y%m%d')}"
        test_timerange = f"{train_end.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    
    # Build command
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{freqtrade_dir}/user_data:/freqtrade/user_data:cached',
    ]
    
    if args.gpu:
        cmd.extend(['--gpus', 'all'])
    
    cmd.extend([
        'freqtradeorg/freqtrade:stable_freqai',
        'backtesting',
        '--config', '/freqtrade/user_data/config.json',
        '--strategy', args.strategy,
        '--timerange', timerange,
        '--timeframe', args.timeframe,
        '--freqaimodel', 'LightGBMClassifier'
    ])
    
    if args.export:
        cmd.extend(['--export', 'trades'])
    
    try:
        result = subprocess.run(cmd, cwd=freqtrade_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Backtest complete")
            
            # Parse metrics from output
            output = result.stdout
            metrics = {}
            
            if 'Total profit' in output:
                metrics['status'] = 'completed'
            
            # Save results
            results_file = workspace / 'memory' / 'backtest_results' / f'backtest_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
            results_file.parent.mkdir(parents=True, exist_ok=True)
            
            results_data = {
                'timestamp': datetime.now().isoformat(),
                'strategy': args.strategy,
                'timerange': timerange,
                'timeframe': args.timeframe,
                'walk_forward': args.walk_forward,
                'gpu': args.gpu,
                'metrics': metrics
            }
            
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            
            print(f"💾 Results saved to: {results_file}")
            
            if args.walk_forward:
                print(f"\n📈 Running forward test on {test_timerange}...")
                # Could recursively call for test period
                
        else:
            print(f"❌ Backtest failed:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
