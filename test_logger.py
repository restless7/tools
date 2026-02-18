"""
Testing Suite Logger Configuration
===================================

Provides structured logging for test execution, results, and system events.
Includes file rotation, console output, and JSON structured logging.
"""

import json
import logging
import logging.handlers
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "test_name"):
            log_data["test_name"] = record.test_name
        if hasattr(record, "test_status"):
            log_data["test_status"] = record.test_status
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration
        if hasattr(record, "coverage"):
            log_data["coverage"] = record.coverage

        return json.dumps(log_data)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for better readability."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    # Emoji indicators
    INDICATORS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🔥",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and emojis."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        indicator = self.INDICATORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # Build message
        message = f"{indicator} {color}[{record.levelname}]{reset} "
        message += f"[{timestamp}] "
        message += f"{record.getMessage()}"

        # Add test-specific info if available
        if hasattr(record, "test_name"):
            message += f" | Test: {record.test_name}"
        if hasattr(record, "test_status"):
            status_color = "\033[32m" if record.test_status == "PASSED" else "\033[31m"
            message += f" | Status: {status_color}{record.test_status}{reset}"
        if hasattr(record, "duration"):
            message += f" | Duration: {record.duration:.2f}s"

        # Add exception if present
        if record.exc_info:
            message += f"\n{reset}"
            message += "".join(traceback.format_exception(*record.exc_info))

        return message


class TestLogger:
    """Centralized logger for test suite."""

    def __init__(self, name: str = "test_suite", log_dir: str = "logs"):
        """
        Initialize test logger.

        Args:
            name: Logger name
            log_dir: Directory for log files
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers

        # Set up handlers
        self._setup_console_handler()
        self._setup_file_handler()
        self._setup_json_handler()
        self._setup_error_handler()

    def _setup_console_handler(self):
        """Set up colored console handler."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredConsoleFormatter())
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self):
        """Set up rotating file handler for all logs."""
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "test_suite.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
            )
        )
        self.logger.addHandler(file_handler)

    def _setup_json_handler(self):
        """Set up JSON structured logging handler."""
        json_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "test_suite.json.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(json_handler)

    def _setup_error_handler(self):
        """Set up separate handler for errors."""
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "errors.log", maxBytes=5 * 1024 * 1024, backupCount=3  # 5 MB
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s\n"
                "Location: %(pathname)s:%(lineno)d in %(funcName)s\n"
                "Message: %(message)s\n"
                "%(separator)s\n",
                defaults={"separator": "-" * 80},
            )
        )
        self.logger.addHandler(error_handler)

    def log_test_start(self, test_name: str, category: str = ""):
        """Log test start."""
        self.logger.info(
            f"Starting test: {test_name}",
            extra={"test_name": test_name, "category": category},
        )

    def log_test_end(
        self, test_name: str, status: str, duration: float, error: Optional[str] = None
    ):
        """Log test end with results."""
        level = logging.INFO if status == "PASSED" else logging.ERROR
        message = f"Test completed: {test_name}"

        extra = {"test_name": test_name, "test_status": status, "duration": duration}

        if error:
            message += f" | Error: {error}"
            extra["error"] = error

        self.logger.log(level, message, extra=extra)

    def log_suite_start(self, total_tests: int, categories: Dict[str, int]):
        """Log test suite start."""
        self.logger.info("=" * 80)
        self.logger.info(f"🚀 STARTING TEST SUITE EXECUTION")
        self.logger.info(f"Total Tests: {total_tests}")
        for category, count in categories.items():
            self.logger.info(f"  - {category}: {count} tests")
        self.logger.info("=" * 80)

    def log_suite_end(self, results: Dict[str, Any]):
        """Log test suite end with summary."""
        self.logger.info("=" * 80)
        self.logger.info(f"✅ TEST SUITE COMPLETED")
        self.logger.info(f"Total: {results['total']}")
        self.logger.info(
            f"✅ Passed: {results['passed']} ({results['pass_rate']:.1f}%)"
        )
        self.logger.info(f"❌ Failed: {results['failed']}")
        self.logger.info(f"⚠️  Errors: {results['errors']}")
        self.logger.info(f"⏱️  Duration: {results['duration']:.2f}s")
        if "coverage" in results:
            self.logger.info(f"📊 Coverage: {results['coverage']:.1f}%")
        self.logger.info("=" * 80)

    def log_coverage(self, coverage_data: Dict[str, Any]):
        """Log coverage information."""
        self.logger.info("📊 Coverage Report:")
        for module, data in coverage_data.items():
            coverage = data.get("coverage", 0)
            color_code = "🟢" if coverage >= 80 else "🟡" if coverage >= 60 else "🔴"
            self.logger.info(
                f"  {color_code} {module}: {coverage:.1f}% "
                f"({data.get('statements', 0)} statements, {data.get('missing', 0)} missing)"
            )

    def log_performance(self, test_name: str, metrics: Dict[str, float]):
        """Log performance metrics."""
        self.logger.info(
            f"⚡ Performance: {test_name}", extra={"test_name": test_name, **metrics}
        )
        for metric, value in metrics.items():
            self.logger.debug(f"  - {metric}: {value}")

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message."""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)


# Global logger instance
_test_logger: Optional[TestLogger] = None


def get_logger(name: str = "test_suite") -> TestLogger:
    """Get or create global test logger instance."""
    global _test_logger
    if _test_logger is None:
        _test_logger = TestLogger(name)
    return _test_logger


def configure_pytest_logging():
    """Configure pytest to use our custom logger."""
    import pytest

    # Get our logger
    logger = get_logger()

    # Create pytest plugin
    class LoggingPlugin:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_protocol(self, item, nextitem):
            """Log test execution."""
            test_name = item.nodeid
            logger.log_test_start(test_name)

            start_time = datetime.now()
            outcome = yield
            duration = (datetime.now() - start_time).total_seconds()

            result = outcome.get_result()
            if hasattr(result, "passed") and result.passed:
                logger.log_test_end(test_name, "PASSED", duration)
            elif hasattr(result, "failed") and result.failed:
                logger.log_test_end(
                    test_name,
                    "FAILED",
                    duration,
                    error=str(result.longrepr) if hasattr(result, "longrepr") else None,
                )
            else:
                logger.log_test_end(test_name, "SKIPPED", duration)

    return LoggingPlugin()


if __name__ == "__main__":
    # Example usage
    logger = get_logger()

    logger.info("Testing logger functionality")
    logger.log_test_start("test_example", "unit")
    logger.log_test_end("test_example", "PASSED", 0.5)

    logger.log_coverage(
        {
            "ice_pipeline.api": {"coverage": 68.0, "statements": 183, "missing": 58},
            "ice_pipeline.ingestion": {
                "coverage": 94.0,
                "statements": 108,
                "missing": 6,
            },
        }
    )

    logger.info("Logger test complete")
