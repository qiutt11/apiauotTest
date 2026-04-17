"""日志模块。

基于 loguru 实现，提供：
    - setup_logger(): 初始化日志（输出到控制台 + 日期文件）
    - log_request(): 格式化记录一次完整的 API 请求/响应信息

日志文件存储在 logs/ 目录下，按日期命名（如 2026-04-17.log），保留 7 天。
"""

import os
from datetime import datetime

from loguru import logger as _loguru_logger


def setup_logger(log_dir: str = "logs") -> _loguru_logger.__class__:
    """初始化日志系统。

    - 创建日志目录
    - 添加文件 sink（按天轮转，保留 7 天）
    - 添加控制台 sink（带颜色）

    Args:
        log_dir: 日志文件存储目录

    Returns:
        配置好的 loguru logger 实例
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    # 只移除默认的 stderr handler（id=0），不影响其他已注册的 handler
    try:
        _loguru_logger.remove(0)
    except ValueError:
        pass  # 已被移除过

    # 文件输出：按天轮转，保留 7 天
    _loguru_logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        encoding="utf-8",
        rotation="1 day",
        retention="7 days",
    )

    # 控制台输出
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
    """格式化记录一次完整的 API 请求/响应信息。

    输出格式示例：
        ========== 用户登录 > 登录成功 ==========
        → POST https://api.example.com/api/login
        → Headers: {"Content-Type": "application/json"}
        → Body: {"username": "admin"}
        ← Status: 200 | Time: 128ms
        ← Response: {"code": 0, "data": {...}}
        ✓ Extract: token = eyJ...
        ✓ Validate: eq PASS
    """
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
