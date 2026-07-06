import logging
from pathlib import Path
import sys


def setup_logging():
    logger = logging.getLogger("scanner")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(getattr(handler, "_scanner_stream_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_formatter())
        handler._scanner_stream_handler = True
        logger.addHandler(handler)

    return logger


def add_file_handler(logger: logging.Logger, log_file: str | Path) -> logging.Handler:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(_formatter())
    logger.addHandler(handler)
    return handler


def remove_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    logger.removeHandler(handler)
    handler.close()


def _formatter() -> logging.Formatter:
    return logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
