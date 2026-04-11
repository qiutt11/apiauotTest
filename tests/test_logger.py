import os
import re


def test_logger_creates_log_file(tmp_path):
    from common.logger import setup_logger

    log_dir = str(tmp_path / "logs")
    logger = setup_logger(log_dir=log_dir)
    logger.info("test message")

    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "test message" in content


def test_logger_formats_request(tmp_path):
    from common.logger import setup_logger, log_request

    log_dir = str(tmp_path / "logs")
    logger = setup_logger(log_dir=log_dir)
    log_request(
        logger=logger,
        module="用户登录",
        name="登录成功",
        method="POST",
        url="https://test.com/api/login",
        headers={"Content-Type": "application/json"},
        body={"username": "admin"},
        status_code=200,
        elapsed_ms=128,
        response={"code": 0},
    )

    log_files = os.listdir(log_dir)
    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "用户登录" in content
    assert "登录成功" in content
    assert "POST" in content
    assert "200" in content
