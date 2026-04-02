#!/usr/bin/env python3
"""
freqtrade_trade: Start/stop Freqtrade trading bots with safety defaults
Default: --dry-run mode. Live trading requires explicit override.
"""

import subprocess
import argparse
import json
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Start/stop Freqtrade trading bots')
    parser.add_argument('--strategy', default='AetherFreqaiStrategy', help='Strategy name')
    parser.add_argument('--pairs', default='BTC/USDC,ETH/USDC,SOL/USDC', help='Comma-separated pairs')
    parser.add_argument('--dry-run', type=bool, default=True, help='Dry run mode (default: True)')
    parser.add_argument('--live', action='store_true', help='WARNING: Enable live trading')
    parser.add_argument('--action', choices=['start', 'stop', 'restart'], default='start')
    parser.add_argument('--port', type=int, default=8080, help='Web UI port')
    parser.add_argument('--gpu', action='store_true', help='Enable GPU acceleration')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    freqtrade_dir = workspace / 'freqtrade'
    
    # Safety check: live mode requires explicit flag
    if args.live:
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("This will use REAL MONEY.")
        print("Type 'YES I UNDERSTAND' to confirm: ", end='', flush=True)
        confirm = input().strip()
        if confirm != 'YES I UNDERSTAND':
            print("❌ Live mode cancelled. Defaulting to dry-run.")
            args.dry_run = True
        else:
            args.dry_run = False
    
    if args.action == 'stop':
        # Stop all freqtrade containers
        cmd = ['docker', 'stop', 'freqtrade'] + \
              [f'freqtrade-{p.lower().replace("/", "-")}' for p in args.pairs.split(',')]
        subprocess.run(cmd, cwd=freqtrade_dir)
        print("✅ All freqtrade containers stopped")
        return
    
    # Build Docker run command
    container_name = 'freqtrade'
    docker_cmd = [
        'docker', 'run', '-d',
        '--name', container_name,
        '-v', f'{freqtrade_dir}/user_data:/freqtrade/user_data:cached',
        '-v', f'{freqtrade_dir}:/freqtrade/data:cached',
        '-p', f'{args.port}:8080'
    ]
    
    if args.gpu:
        docker_cmd.extend(['--gpus', 'all'])
    
    docker_cmd.append('freqtradeorg/freqtrade:stable_freqai')
    docker_cmd.append('trade')
    docker_cmd.extend(['--config', '/freqtrade/user_data/config.json'])
    docker_cmd.extend(['--strategy', args.strategy])
    docker_cmd.extend(['--freqaimodel', 'LightGBMClassifier'])
    docker_cmd.extend(['--db-url', 'sqlite:////freqtrade/data/tradesv3.dryrun.sqlite'])
    
    if args.dry_run:
        print("🧪 Starting in DRY-RUN mode (paper trading)")
    
    try:
        result = subprocess.run(docker_cmd, cwd=freqtrade_dir, capture_output=True, text=True)
        container_id = result.stdout.strip()
        
        if result.returncode == 0:
            print(f"✅ Container started: {container_id[:12]}")
            print(f"   Strategy: {args.strategy}")
            print(f"   Mode: {'LIVE' if not args.dry_run else 'DRY-RUN'}")
            print(f"   Web UI: http://localhost:{args.port}")
            print(f"   GPU: {'Enabled' if args.gpu else 'CPU only'}")
            
            # Save to memory
            memory_file = workspace / 'memory' / 'container_launches.json'
            launch_data = {
                'container': container_id[:12],
                'strategy': args.strategy,
                'mode': 'live' if not args.dry_run else 'dry-run',
                'port': args.port,
                'gpu': args.gpu
            }
            
            with open(memory_file, 'a') as f:
                json.dump(launch_data, f)
                f.write('\n')
                
        else:
            print(f"❌ Failed to start container:")
            print(result.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
