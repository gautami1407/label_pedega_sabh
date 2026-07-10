"""
Structured logging configuration for production-grade application.

Provides:
- JSON-formatted logs for machine parsing
- Request/Response logging middleware
- Structured error logging
- Development and production modes
"""
from __future__ import annotations

import json
import logging
import logging.config
from datetime import datetime
from typing import Any

from lps.core.config import get_settings


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Outputs logs as JSON objects for better parsing and analysis in production.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        """
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)

        return json.dumps(log_obj)


class PlainFormatter(logging.Formatter):
    """
    Human-readable formatter for development.
    """

    _format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    _date_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self._format, datefmt=self._date_format)


def setup_logging() -> None:
    """
    Configure application-wide logging based on settings.
    
    Called once at application startup.
    """
    settings = get_settings()

    # Determine formatter based on log format setting
    if settings.log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = PlainFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )
    logging.getLogger("sqlalchemy.pool").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )
    logging.getLogger("uvicorn").setLevel(getattr(logging, settings.log_level))
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, settings.log_level))


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


# Module-level logger
logger = get_logger(__name__)


class LogContext:
    """
    Context manager for adding structured data to logs.
    
    Usage:
        with LogContext(user_id=user_id, request_id=request_id):
            logger.info("Processing request")
    """

    def __init__(self, **context_data: Any):
        """Initialize context with data."""
        self.context_data = context_data
        self.token = None

    def __enter__(self):
        """Enter context."""
        # Store current context in task-local storage if available
        # For now, just return self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass

    def log(self, message: str, level: str = "INFO", **extra_data: Any) -> None:
        """
        Log a message with context data.
        """
        logger_instance = get_logger(__name__)
        log_method = getattr(logger_instance, level.lower(), logger_instance.info)

        # Combine context data and extra data
        data = {**self.context_data, **extra_data}

        # Create a log record with extra data
        log_method(message, extra={"extra_data": data})
