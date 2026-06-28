"""Utility functions: config loading, price helpers, time helpers."""

import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger


def load_config(path: str = "config/settings.yaml") -> dict:
    """Load YAML config and substitute ${ENV_VAR} placeholders.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Parsed configuration dictionary with env vars resolved.

    Raises:
        FileNotFoundError: If config file doesn't exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = config_path.read_text(encoding="utf-8")

    # Replace ${ENV_VAR} with actual environment variable values
    def _replace_env(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name, "")
        if not value:
            logger.warning("Environment variable {} is not set", var_name)
        return value

    resolved = re.sub(r"\$\{(\w+)\}", _replace_env, raw)
    config = yaml.safe_load(resolved)
    logger.info("Configuration loaded from {}", path)
    return config


def utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def is_weekday(dt: Optional[datetime] = None) -> bool:
    """Check if given datetime (or now) is a weekday (Mon–Fri)."""
    if dt is None:
        dt = utc_now()
    return dt.weekday() < 5


def time_until(target_hour: int, target_minute: int) -> timedelta:
    """Calculate time remaining until a specific UTC time today.

    Args:
        target_hour: Target hour in UTC (0-23).
        target_minute: Target minute (0-59).

    Returns:
        Timedelta until target time. Negative if target has passed.
    """
    now = utc_now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    return target - now


def points_to_price(points: float, point_size: float) -> float:
    """Convert points to price difference.

    Args:
        points: Number of points.
        point_size: Symbol's point size (e.g. 0.001 for XAUUSD).

    Returns:
        Price difference as float.
    """
    return points * point_size


def price_to_points(price_diff: float, point_size: float) -> int:
    """Convert price difference to points.

    Args:
        price_diff: Absolute price difference.
        point_size: Symbol's point size.

    Returns:
        Number of points as integer.
    """
    if point_size == 0:
        return 0
    return int(round(abs(price_diff) / point_size))


def format_price(price: float, digits: int = 3) -> str:
    """Format price to specified decimal places.

    Args:
        price: Price value.
        digits: Number of decimal places.

    Returns:
        Formatted price string.
    """
    return f"{price:.{digits}f}"


def ensure_dir(path: str) -> Path:
    """Ensure directory exists, create if not.

    Args:
        path: Directory path.

    Returns:
        Path object of the directory.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
