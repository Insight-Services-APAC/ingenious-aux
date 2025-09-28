"""Simple structured logging for standalone package."""

import logging
import sys
from typing import Any, Dict, Optional


def get_logger(name: str) -> logging.Logger:
    """Get a logger with structured formatting."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


class StructuredLogger:
    """Simple structured logger."""
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(f"{message} {kwargs}")
    
    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(f"{message} {kwargs}")
    
    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(f"{message} {kwargs}")
    
    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(f"{message} {kwargs}")