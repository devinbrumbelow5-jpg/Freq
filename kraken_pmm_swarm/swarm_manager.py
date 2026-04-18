"""
Swarm Manager - Orchestrates all 6 PMM bots and provides dashboard.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import sys

from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box

from kraken_paper_client import KrakenPaperClient
from coinbase_paper_client import CoinbasePaperClient
from aggressive_mm import PassiveMarketMaker, AMMConfig
from database import DatabaseManager
from utils import load_config, format_usd, format_pct


class SwarmManager:
    """
    Manages 6 PMM bots with unified dashboard.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.console = Console()
        
        # Initialize Coinbase client (more stable than Kraken)
        self.client = CoinbasePaperClient(
            paper_balances=config['paper_balances'],
            max_slippage_pct=config['swarm']['max_slippage_pct']
        )
        
        # Initialize database
        self.db = DatabaseManager(config['database']['path'])
        
        # Initialize bots - PASSIVE MM
        self.bots: Dict[str, PassiveMarketMaker] = {}
        self._init_bots(config['bots'])
        
        # Dashboard state
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._dashboard_task: Optional[asyncio.Task] = None
    
    def _init_bots(self, bot_configs: List[Dict]):
        """Initialize passive MM bots."""
        for i, cfg in enumerate(bot_configs):
            bot_id = f"pmm_{i+1}"
            config = AMMConfig(
                pair=cfg['pair'],
                min_edge_bps=2,  # 2 bps maker edge
                order_amount_usd=100,  # Reduced to $100
                max_position_pct=cfg['max_position_pct']
            )
            self.bots[bot_id] = PassiveMarketMaker(
                bot_id=bot_id,
                config=config,
                client=self.client,
                database=self.db
            )
    
    async def start(self):
        """Start the swarm."""
        self._running = True
        
        # Connect database
        await self.db.connect()
        self.console.print("[green]Database connected[/green]")
        
        # Start Kraken client WebSockets
        pairs = [bot.config.pair for bot in self.bots.values()]
        await self.client.start(pairs)
        self.console.print(f"[green]Kraken WebSocket started for {len(pairs)} pairs[/green]")
        
        # Wait for order books to populate
        self.console.print("[yellow]Waiting for order books...[/yellow]")
        await asyncio.sleep(2)
        
        # Start all bots
        for bot_id, bot in self.bots.items():
            await bot.start()
            self.console.print(f"[green]Bot {bot_id} ({bot.config.pair}) started[/green]")
        
        # Start dashboard
        self._dashboard_task = asyncio.create_task(self._run_dashboard())
        
        self.console.print("\n[bold green]Swarm running. Press Ctrl+C to stop.[/bold green]\n")
    
    async def stop(self):
        """Stop the swarm gracefully."""
        self._running = False
        
        # Stop dashboard
        if self._dashboard_task:
            self._dashboard_task.cancel()
            try:
                await self._dashboard_task
            except asyncio.CancelledError:
                pass
        
        # Stop all bots
        for bot_id, bot in self.bots.items():
            await bot.stop()
            self.console.print(f"[red]Bot {bot_id} stopped[/red]")
        
        # Stop client
        await self.client.stop()
        
        # Close database
        await self.db.close()
        self.console.print("[red]Database closed[/red]")
    
    async def _run_dashboard(self):
        """Run dashboard updates."""
        try:
            while self._running:
                self._render_dashboard()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
    
    def _render_dashboard(self):
        """Render dashboard to console - simplified to avoid blocking."""
        # Simple text output instead of rich formatting
        print("\n" + "="*60)
        print("Kraken PMM Swarm Dashboard")
        print("="*60)
        
        for bot_id, bot in self.bots.items():
            stats = bot.get_stats()
            status = "ON" if stats['is_running'] else "OFF"
            pair = bot.config.pair
            fills = stats['total_fills']
            pos = stats.get('position', 0)
            print(f"{bot_id}: {pair} [{status}] Fills: {fills} Pos: {pos:.6f}")
        
        # Show balances
        try:
            balances = self.client.get_all_balances()
            usd_bal = balances.get('USD', {}).get('available', 0)
            print(f"\nUSD Balance: ${usd_bal:.2f}")
        except:
            pass
        
        print("\nPress Ctrl+C to stop")
        print("="*60)
    
    async def get_swarm_stats(self) -> Dict:
        """Get aggregate swarm statistics."""
        stats = {
            'bots_running': sum(1 for b in self.bots.values() if b.is_running),
            'total_bots': len(self.bots),
            'total_fills': sum(b.total_fills for b in self.bots.values()),
            'bots': {}
        }
        
        for bot_id, bot in self.bots.items():
            stats['bots'][bot_id] = bot.get_stats()
        
        return stats
