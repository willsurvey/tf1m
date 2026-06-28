"""Logger setup using loguru with file rotation and console output."""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure loguru logger for console and file output.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory path for log files.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console handler — colorized
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler — rotating
    logger.add(
        str(log_path / "bot_{time:YYYY-MM-DD}.log"),
        level=log_level,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{module}:{function}:{line} | {message}"
        ),
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    # Separate error log
    logger.add(
        str(log_path / "errors_{time:YYYY-MM-DD}.log"),
        level="ERROR",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{module}:{function}:{line} | {message}\n{exception}"
        ),
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    logger.info("Logger initialized | level={} | dir={}", log_level, log_dir)
