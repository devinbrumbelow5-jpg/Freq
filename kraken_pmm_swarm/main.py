#!/usr/bin/env python3
"""
Kraken PMM Swarm - Main Entry Point
Production-ready CCXT-based Perpetual Market Making System

Features:
- 6 independent PMM bots for BTC, ETH, SOL, AVAX, LINK, AAVE
- Real-time WebSocket order book data
- 100% paper trading simulation
- Rich terminal dashboard
- SQLite persistence
"""

import asyncio
import sys
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from swarm_manager import SwarmManager
from utils import setup_logging, load_config


async def main():
    """Main entry point for the Kraken PMM Swarm."""
    
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Kraken PMM Swarm Starting")
    logger.info("=" * 60)
    
    # Load configuration
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Initialize swarm manager
    swarm = SwarmManager(config)
    
    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, stopping swarm...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the swarm
        await swarm.start()
        logger.info("Swarm started successfully")
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
    except Exception as e:
        logger.error(f"Swarm error: {e}", exc_info=True)
    finally:
        # Stop the swarm gracefully
        logger.info("Stopping swarm...")
        await swarm.stop()
        logger.info("Swarm stopped")
    
    logger.info("=" * 60)
    logger.info("Kraken PMM Swarm Shutdown Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
        sys.exit(0)
