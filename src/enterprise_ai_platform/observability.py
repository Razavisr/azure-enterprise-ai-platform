import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

import structlog


def configure_logging(level_name: str) -> None:
    level = logging.getLevelNamesMapping().get(level_name.upper())
    if level is None:
        raise ValueError(f"Unknown log level: {level_name}")

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@contextmanager
def measure_stage(stage: str) -> Iterator[None]:
    started = perf_counter()
    logger = structlog.get_logger("enterprise_ai_platform.workflow")

    try:
        yield
    except Exception as exc:
        logger.error(
            "workflow_stage",
            stage=stage,
            outcome="error",
            error_type=type(exc).__name__,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        raise
    else:
        logger.info(
            "workflow_stage",
            stage=stage,
            outcome="ok",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
