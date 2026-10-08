"""Structured logging configuration."""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging for the whole application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    # Keep noisy third-party libraries reasonable.
    for noisy in ("pyogrio", "fiona", "matplotlib", "PIL", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
