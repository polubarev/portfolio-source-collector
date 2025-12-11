import logging
import sys
from typing import Optional, Union


def configure_logging(
    level: Union[int, str] = logging.INFO, logger_name: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return a logger. Reuses existing handlers to avoid duplicates.
    """
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
