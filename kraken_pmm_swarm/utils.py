"""
Utility functions for the Kraken PMM Swarm.
"""

import logging
import yaml
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import structlog
from pythonjsonlogger import jsonlogger


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, uses default config.yaml
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> structlog.BoundLogger:
    """
    Setup structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        logging.getLogger().addHandler(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if log_file else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger("kraken_pmm_swarm")


def format_price(price: float, decimals: int = 2) -> str:
    """Format price with appropriate decimals."""
    return f"{price:.{decimals}f}"


def format_pct(value: float) -> str:
    """Format percentage value."""
    return f"{value * 100:.2f}%"


def format_usd(value: float) -> str:
    """Format USD value."""
    if abs(value) >= 1000:
        return f"${value:,.2f}"
    return f"${value:.2f}"


def calculate_mid_price(bid: float, ask: float) -> float:
    """Calculate mid price from bid and ask."""
    return (bid + ask) / 2


def calculate_spread(bid: float, ask: float) -> float:
    """Calculate spread as percentage of mid price."""
    mid = calculate_mid_price(bid, ask)
    if mid == 0:
        return 0.0
    return (ask - bid) / mid


def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(datetime.utcnow().timestamp() * 1000)


def parse_pair(pair: str) -> tuple:
    """Parse trading pair into base and quote."""
    parts = pair.split('/')
    return parts[0], parts[1]


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default on zero denominator."""
    if denominator == 0:
        return default
    return numerator / denominator


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_second: float = 10.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    async def acquire(self):
        """Acquire permission to make a call."""
        import time
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


class ExponentialBackoff:
    """Exponential backoff for reconnections."""
    
    def __init__(self, base: float = 1.0, max_delay: float = 60.0):
        self.base = base
        self.max_delay = max_delay
        self.attempt = 0
    
    def next_delay(self) -> float:
        """Get next delay value."""
        delay = min(self.base * (2 ** self.attempt), self.max_delay)
        self.attempt += 1
        return delay
    
    def reset(self):
        """Reset backoff counter."""
        self.attempt = 0


# Import asyncio at the end to avoid circular imports
import asyncio
