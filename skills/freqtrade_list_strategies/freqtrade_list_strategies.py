#!/usr/bin/env python3
"""
freqtrade_list_strategies: List available strategies in freqtrade
"""

import os
import argparse
from pathlib import Path
import ast

def extract_strategy_info(file_path):
    """Extract strategy name and description from Python file"""
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if 'IStrategy' in ast.unparse(base) or 'Strategy' in ast.unparse(base):
                        # Extract docstring
                        docstring = ast.get_docstring(node)
                        return {
                            'name': node.name,
                            'description': docstring[:100] + '...' if docstring and len(docstring) > 100 else docstring,
                            'freqai_compatible': self.check_freqai_compatible(file_path, node.name)
                        }
    except Exception as e:
        return {'name': file_path.stem, 'error': str(e)}
    
    return None

def check_freqai_compatible(file_path, class_name):
    """Check if strategy has FreqAI methods"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return 'feature_engineering' in content or 'set_freqai_targets' in content
    except:
        return False

def main():
    parser = argparse.ArgumentParser(description='List Freqtrade strategies')
    parser.add_argument('--freqai-only', action='store_true', 
                       help='Show only FreqAI-compatible strategies')
    parser.add_argument('--detailed', action='store_true', 
                       help='Show detailed strategy info')
    
    args = parser.parse_args()
    
    workspace = Path('/root/.openclaw/workspace')
    strategies_dir = workspace / 'freqtrade' / 'user_data' / 'strategies'
    
    if not strategies_dir.exists():
        print(f"❌ Strategies directory not found: {strategies_dir}")
        return
    
    strategies = []
    
    print(f"🔍 Scanning strategies in: {strategies_dir}")
    print("-" * 60)
    
    for file_path in strategies_dir.glob('*.py'):
        if file_path.name.startswith('__'):
            continue
        
        info = extract_strategy_info(file_path)
        if info:
            strategies.append(info)
    
    # Sort by name
    strategies.sort(key=lambda x: x['name'])
    
    # Filter if freqai-only
    if args.freqai_only:
        strategies = [s for s in strategies if s.get('freqai_compatible', False)]
        print(f"📊 FreqAI-Compatible Strategies: {len(strategies)}")
    else:
        print(f"📊 Total Strategies: {len(strategies)}")
    
    print("-" * 60)
    
    for strategy in strategies:
        if args.detailed:
            print(f"\n🔹 {strategy['name']}")
            if strategy.get('description'):
                print(f"   Description: {strategy['description']}")
            print(f"   FreqAI: {'✅' if strategy.get('freqai_compatible') else '❌'}")
        else:
            freqai_marker = "⚡" if strategy.get('freqai_compatible') else " "
            desc = strategy.get('description', '')[:40] if strategy.get('description') else 'No description'
            print(f"{freqai_marker} {strategy['name']:<30} {desc}")
    
    print(f"\n⚡ = FreqAI-compatible strategy")

if __name__ == '__main__':
    main()
