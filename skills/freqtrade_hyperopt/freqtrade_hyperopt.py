#!/usr/bin/env python3
"""
freqtrade_hyperopt: Run hyperparameter optimization with GPU support
"""

import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='Run Freqtrade hyperopt')
    parser.add_argument('--strategy', default='AetherFreqaiStrategy', help='Strategy name')
    parser.add_argument('--epochs', type=int, default=100, help='Number of epochs')
    parser.add_argument('--spaces', default='buy sell roi trailing stoploss', 
                       help='Hyperopt spaces')
    parser.add_argument('--loss', default='SharpeHyperOptLossDaily', 
                       help='Loss function')
    parser.add_argument('--timerange', default='30', 
                       help='Days to optimize (e.g., "30" for last 30 days)')
    parser.add_argument('--gpu', action='store_true', help='Enable GPU acceleration')
    parser.add_argument('--aggressive', action='store_true', 
                       help='Run 500 epochs on 14 days')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    
    # Adjust parameters for aggressive mode
    if args.aggressive:
        args.epochs = 500
        args.timerange = '14'
        print("🚀 AGGRESSIVE MODE: 500 epochs on 14 days of data")
    
    # Calculate timerange
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - __import__('datetime').timedelta(days=int(args.timerange))).strftime('%Y%m%d')
    timerange = f"{start_date}-{end_date}"
    
    print(f"🔬 Starting hyperopt: {args.epochs} epochs")
    print(f"   Strategy: {args.strategy}")
    print(f"   Timerange: {timerange}")
    print(f"   Spaces: {args.spaces}")
    print(f"   Loss function: {args.loss}")
    
    # Build command
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{freqtrade_dir}/user_data:/freqtrade/user_data:cached',
    ]
    
    if args.gpu:
        cmd.extend(['--gpus', 'all'])
        print(f"   GPU: Enabled (LightGBM/XGBoost)")
    
    cmd.extend([
        'freqtradeorg/freqtrade:stable_freqai',
        'hyperopt',
        '--config', '/freqtrade/user_data/config.json',
        '--strategy', args.strategy,
        '-e', str(args.epochs),
        '--spaces'] + args.spaces.split() + [
        '--hyperopt-loss', args.loss,
        '--timerange', timerange,
        '--freqaimodel', 'LightGBMClassifier'
    ])
    
    try:
        result = subprocess.run(cmd, cwd=freqtrade_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Hyperopt complete")
            
            # Save results
            results_file = freqtrade_dir / 'user_data' / 'hyperopt_results' / f'winning_params_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
            results_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy last result
            last_result = freqtrade_dir / 'user_data' / 'hyperopt_results' / '.last_result.json'
            if last_result.exists():
                import shutil
                shutil.copy(last_result, results_file)
                print(f"💾 Results saved to: {results_file}")
            
            # Log to memory
            memory_file = workspace / 'memory' / 'hyperopt_log.json'
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'strategy': args.strategy,
                'epochs': args.epochs,
                'timerange': timerange,
                'aggressive': args.aggressive,
                'gpu': args.gpu
            }
            
            with open(memory_file, 'a') as f:
                json.dump(log_entry, f)
                f.write('\n')
                
        else:
            print(f"❌ Hyperopt failed:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
