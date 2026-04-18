#!/usr/bin/env python3
"""
Condor API Server (Standalone)
Runs Condor web API without Telegram bot.
"""

import asyncio
import logging
import signal
import uvicorn
from pathlib import Path

# Add condor to path
import sys
sys.path.insert(0, "/root/.openclaw/workspace/condor")

from condor.web.app import create_app
from condor.web.ws_manager import get_ws_manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Run the Condor API server."""
    # Create web app
    web_app = create_app()
    
    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=8001,  # Changed from 8000 to avoid conflict
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    
    # Start WebSocket manager
    get_ws_manager().start()
    
    logger.info("Starting Condor API Server on port 8001")
    
    # Handle shutdown signals
    shutdown_event = asyncio.Event()
    
    def _signal_handler():
        shutdown_event.set()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)
    
    # Run uvicorn as a task
    web_task = asyncio.create_task(server.serve())
    
    # Wait until shutdown signal
    await shutdown_event.wait()
    
    logger.info("Shutting down...")
    server.should_exit = True
    await web_task


if __name__ == "__main__":
    asyncio.run(main())
