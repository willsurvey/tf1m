"""XAUUSD AGGRO V6 Trading Bot — Entry Point.

Usage:
    python -m src.main                    # Normal mode
    python -m src.main --dry-run          # Dry run (no real trades)
    python -m src.main --config path.yaml # Custom config
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Ensure project root is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logger
from src.utils.helpers import load_config, ensure_dir
from src.bot import TradingBot


def main() -> None:
    """Parse arguments, load config, and start the trading bot."""
    parser = argparse.ArgumentParser(
        description="XAUUSD AGGRO V6 — Automated Trading Bot (MT5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.main              # Start in live mode\n"
            "  python -m src.main --dry-run    # Start without real trades\n"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing real trades (signals are logged only)",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to YAML configuration file (default: config/settings.yaml)",
    )
    args = parser.parse_args()

    # Load environment variables from .env
    load_dotenv()

    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Copy .env.example to .env and config/settings.yaml first.")
        sys.exit(1)

    # Setup logging
    log_level = config.get("logging", {}).get("level", "INFO")
    setup_logger(log_level, "logs")

    # Ensure data directories exist
    ensure_dir("logs")
    ensure_dir("data")

    # Print startup banner
    logger.info("=" * 55)
    logger.info("  XAUUSD AGGRO V6 — Automated Trading Bot")
    logger.info("  Mode: {}", "DRY RUN 🔵" if args.dry_run else "LIVE 🔴")
    logger.info("  Config: {}", args.config)
    logger.info("=" * 55)

    # Create and run bot
    bot = TradingBot(config, dry_run=args.dry_run)
    bot.run()


if __name__ == "__main__":
    main()
