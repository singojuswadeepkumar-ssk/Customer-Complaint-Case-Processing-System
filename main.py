"""
Main entry-point for the AI-Powered Customer Complaint & Case Processing System.

Usage:
    python main.py                       # uses default data/ and output/ directories
    python main.py --data <path>         # custom data directory
    python main.py --output <path>       # custom output directory
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from src.workflow import run_pipeline
from src.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Customer Complaint & Case Processing System"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data"),
        help="Directory containing complaint documents (default: data/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory for generated outputs (default: output/)",
    )
    return parser.parse_args()


def main() -> None:
    """Application entry-point."""
    logger.info("=" * 70)
    logger.info("STEP 0/6 | Starting app: AI-Powered Complaint & Case Processing System")
    logger.info("=" * 70)
    args = parse_args()
    logger.info("Configuration | data_dir=%s | output_dir=%s", args.data, args.output)

    try:
        results = run_pipeline(data_dir=args.data, output_dir=args.output)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Fatal error — pipeline aborted: %s", exc, exc_info=True)
        raise

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    logger.info(
        "App finished. %d/%d complaints processed successfully (%d failed).",
        success_count, len(results), fail_count,
    )


if __name__ == "__main__":
    main()
