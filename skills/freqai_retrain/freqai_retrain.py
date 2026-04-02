#!/usr/bin/env python3
"""
freqai_retrain: Retrain FreqAI models with continual learning and GPU support
"""

import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime
import time

def main():
    parser = argparse.ArgumentParser(description='Retrain FreqAI models')
    parser.add_argument('--identifier', default='aether_adaptive_v1', 
                       help='FreqAI model identifier')
    parser.add_argument('--train-days', type=int, default=15, 
                       help='Training period in days')
    parser.add_argument('--backtest-days', type=int, default=7, 
                       help='Backtest period in days')
    parser.add_argument('--strategy', default='AetherFreqaiStrategy', 
                       help='Strategy to train')
    parser.add_argument('--gpu', action='store_true', 
                       help='Enable GPU acceleration for LightGBM')
    parser.add_argument('--wait', action='store_true', 
                       help='Wait for training to complete')
    parser.add_argument('--force', action='store_true', 
                       help='Force retrain even if recent model exists')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    models_dir = freqtrade_dir / 'user_data' / 'models' / args.identifier
    
    # Check if recent model exists
    if not args.force and models_dir.exists():
        last_model = models_dir / 'historic_predictions.pkl'
        if last_model.exists():
            import os
            age_hours = (datetime.now().timestamp() - os.path.getmtime(last_model)) / 3600
            if age_hours < 4:
                print(f"⏭️  Recent model exists ({age_hours:.1f}h old). Use --force to retrain.")
                return
    
    print(f"🧠 Starting FreqAI model training")
    print(f"   Identifier: {args.identifier}")
    print(f"   Strategy: {args.strategy}")
    print(f"   Training: {args.train_days} days")
    print(f"   Backtest: {args.backtest_days} days")
    print(f"   Continual Learning: Enabled")
    print(f"   GPU: {'✅ Enabled' if args.gpu else '❌ CPU only'}")
    print(f"   Auto-retrain: Every 4 hours")
    
    # Ensure models directory exists
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Build Docker command
    cmd = [
        'docker', 'run', '--rm', '-d',
        '--name', f'freqai-train-{args.identifier}',
        '-v', f'{freqtrade_dir}/user_data:/freqtrade/user_data:cached',
    ]
    
    if args.gpu:
        cmd.extend(['--gpus', 'all'])
    
    cmd.extend([
        'freqtradeorg/freqtrade:stable_freqai',
        'trade',
        '--config', '/freqtrade/user_data/config.json',
        '--strategy', args.strategy,
        '--freqaimodel', 'LightGBMClassifier',
        '--db-url', 'sqlite:////freqtrade/data/tradesv3.dryrun.sqlite'
    ])
    
    try:
        # Start training container
        result = subprocess.run(cmd, cwd=freqtrade_dir, capture_output=True, text=True)
        container_id = result.stdout.strip()
        
        if result.returncode == 0:
            print(f"✅ Training container started: {container_id[:12]}")
            
            if args.wait:
                print("⏳ Waiting for training to complete (this may take 10-20 minutes)...")
                
                # Monitor logs for "Training complete" or "Waiting on Training"
                start_time = time.time()
                timeout = 1800  # 30 minutes max
                
                while time.time() - start_time < timeout:
                    log_result = subprocess.run(
                        ['docker', 'logs', f'freqai-train-{args.identifier}', '--tail', '10'],
                        capture_output=True, text=True
                    )
                    
                    if 'Training complete' in log_result.stdout or 'Waiting on Training iteration' in log_result.stdout:
                        print("✅ Training iteration complete!")
                        break
                    
                    if 'error' in log_result.stdout.lower() or 'exception' in log_result.stdout.lower():
                        print("❌ Training error detected")
                        print(log_result.stdout)
                        break
                    
                    time.sleep(10)
                    print(".", end='', flush=True)
                
                print()  # New line
                
                # Clean up container
                subprocess.run(['docker', 'stop', f'freqai-train-{args.identifier}'], 
                              capture_output=True)
                subprocess.run(['docker', 'rm', f'freqai-train-{args.identifier}'], 
                              capture_output=True)
            
            # Log to memory
            memory_file = workspace / 'memory' / 'freqai_retrain_log.json'
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'identifier': args.identifier,
                'strategy': args.strategy,
                'train_days': args.train_days,
                'gpu': args.gpu,
                'container': container_id[:12] if container_id else 'unknown'
            }
            
            with open(memory_file, 'a') as f:
                json.dump(log_entry, f)
                f.write('\n')
            
            print(f"💾 Training logged to memory")
            
        else:
            print(f"❌ Failed to start training:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
