"""
logging_utils.py — File-based run logging with timestamps and duration
tracking, on top of Python's standard `logging` (all other modules in this
package already log via `logging.getLogger("climate_indices.<module>")` --
this just wires up a proper file handler + a run-timer context manager so
those messages land in outputs/logs/ instead of only stdout).
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path


def setup_logging(
    log_dir: str | Path,
    level: int = logging.INFO,
    run_name: str | None = None,
) -> Path:
    """Configure the root `climate_indices` logger to write to both stdout
    and a timestamped log file under `log_dir`.

    Returns the path to the created log file.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    name_part = f"_{run_name}" if run_name else ""
    log_path = log_dir / f"run{name_part}_{timestamp}.log"

    logger = logging.getLogger("climate_indices")
    logger.setLevel(level)
    logger.handlers.clear()  # avoid duplicate handlers if called more than once

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("Logging initialized -> %s", log_path)
    return log_path


@contextmanager
def timed_step(step_name: str, logger: logging.Logger | None = None):
    """Context manager that logs start/end/duration of a pipeline step.

    Example
    -------
    >>> with timed_step("Computing temperature indices"):
    ...     temp_idx = ci.indices_temp.compute_temperature_indices(...)
    """
    log = logger or logging.getLogger("climate_indices")
    log.info("START: %s", step_name)
    start = time.time()
    try:
        yield
    except Exception:
        elapsed = time.time() - start
        log.error("FAILED: %s (after %.1fs)", step_name, elapsed)
        raise
    else:
        elapsed = time.time() - start
        log.info("DONE: %s (%.1fs)", step_name, elapsed)
