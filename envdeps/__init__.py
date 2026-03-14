import sys

from loguru import logger

logger.disable("envdeps")


def _setup_logging(level: str = "INFO"):
    logger.remove()
    logger.add(sys.stderr, level=level, colorize=True)
    logger.enable("envdeps")
