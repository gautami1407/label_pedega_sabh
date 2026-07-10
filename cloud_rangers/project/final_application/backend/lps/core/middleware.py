"""
FastAPI middleware for request/response logging and observability.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from lps.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all incoming requests and outgoing responses.
    
    Includes:
    - Request ID generation and tracking
    - Timing information
    - Status codes
    - Client information
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log timing/information.
        """
        # Generate or retrieve request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"Incoming {request.method} {request.url.path}",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client": request.client[0] if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", ""),
                }
            },
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        logger.info(
            f"Response {request.method} {request.url.path} - {response.status_code}",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client": request.client[0] if request.client else "unknown",
                }
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for global error handling and logging.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle errors globally.
        """
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.error(
                f"Unhandled exception: {str(e)}",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "path": request.url.path,
                        "exception_type": type(e).__name__,
                    }
                },
                exc_info=True,
            )
            raise
