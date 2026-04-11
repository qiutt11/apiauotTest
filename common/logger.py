import os
from datetime import datetime

from loguru import logger as _loguru_logger


def setup_logger(log_dir: str = "logs") -> _loguru_logger.__class__:
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    try:
        _loguru_logger.remove(0)  # Only remove the default stderr handler
    except ValueError:
        pass  # Already removed
    _loguru_logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        encoding="utf-8",
        rotation="1 day",
        retention="7 days",
    )
    _loguru_logger.add(
        lambda msg: print(msg, end=""),
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        colorize=True,
    )
    return _loguru_logger


def log_request(
    logger,
    module: str,
    name: str,
    method: str,
    url: str,
    headers: dict = None,
    body: dict = None,
    status_code: int = None,
    elapsed_ms: float = None,
    response: dict = None,
    extracts: dict = None,
    validations: list = None,
):
    logger.info(f"{'=' * 10} {module} > {name} {'=' * 10}")
    logger.info(f"→ {method} {url}")
    if headers:
        logger.info(f"→ Headers: {headers}")
    if body:
        logger.info(f"→ Body: {body}")
    if status_code is not None:
        logger.info(f"← Status: {status_code} | Time: {elapsed_ms}ms")
    if response is not None:
        logger.info(f"← Response: {response}")
    if extracts:
        for k, v in extracts.items():
            logger.info(f"✓ Extract: {k} = {v}")
    if validations:
        for v in validations:
            logger.info(f"✓ Validate: {v}")
