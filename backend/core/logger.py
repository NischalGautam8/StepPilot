"""
Structured logging configuration with log rotation for StepPilot.
Uses structlog for structured logging and rotating file handler.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import structlog
from datetime import datetime


def setup_logging(log_level: str = "INFO"):
    """
    Configure structured logging with file rotation.
    
    Logs are written to:
    - Console (stdout) with colored output
    - File at ~/.cursor-king/logs/cursor-king.log with rotation
    
    Rotation: Max 10MB per file, keep 3 backup files
    """
    # Create log directory
    log_dir = Path.home() / ".cursor-king" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cursor-king.log"
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[
            # Console handler
            logging.StreamHandler(sys.stdout),
            # Rotating file handler (10MB max, keep 3 backups)
            RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=3,
                encoding='utf-8'
            )
        ]
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(colors=True)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    
    logger = structlog.get_logger("cursor-king-backend")
    logger.info(
        "logging_initialized",
        log_level=log_level,
        log_file=str(log_file),
        log_dir=str(log_dir)
    )
    
    return logger


def get_logger(name: str = "cursor-king-backend"):
    """Get a structured logger instance"""
    return structlog.get_logger(name)


# Convenience functions for common log patterns
def log_llm_call(logger, provider: str, model: str, tokens: int, latency_ms: float, success: bool):
    """Log an LLM API call with metrics"""
    logger.info(
        "llm_call",
        provider=provider,
        model=model,
        tokens=tokens,
        latency_ms=latency_ms,
        success=success,
        timestamp=datetime.utcnow().isoformat()
    )


def log_step_transition(logger, task_id: str, from_step: int, to_step: int, total_steps: int):
    """Log a task step transition"""
    logger.info(
        "step_transition",
        task_id=task_id,
        from_step=from_step,
        to_step=to_step,
        total_steps=total_steps,
        timestamp=datetime.utcnow().isoformat()
    )


def log_error(logger, error_type: str, error_message: str, context: dict = None):
    """Log an error with context"""
    logger.error(
        "error_occurred",
        error_type=error_type,
        error_message=error_message,
        context=context or {},
        timestamp=datetime.utcnow().isoformat()
    )


def log_websocket_event(logger, event: str, client_id: str, details: dict = None):
    """Log a WebSocket event"""
    logger.info(
        "websocket_event",
        event=event,
        client_id=client_id,
        details=details or {},
        timestamp=datetime.utcnow().isoformat()
    )
