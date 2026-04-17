"""HTTP 请求模块。

封装 requests 库，发送 HTTP 请求并返回标准化的响应字典。
自动处理超时、连接异常等错误，不会抛出异常。

返回格式：
    {
        "status_code": 200,          # HTTP 状态码，异常时为 None
        "body": {...},               # 响应 body（JSON 解析后的 dict），异常时为 None
        "headers": {...},            # 响应头
        "elapsed_ms": 128.5,         # 请求耗时（毫秒）
        "error": None,               # 错误信息，成功时为 None
    }
"""

from typing import Any

import requests


def send_request(
    method: str,
    url: str,
    headers: dict = None,
    body: dict = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """发送 HTTP 请求并返回标准化响应。

    Args:
        method: HTTP 方法（GET/POST/PUT/DELETE/PATCH）
        url: 完整的请求 URL
        headers: 请求头（可选）
        body: 请求体，会以 JSON 格式发送（可选）
        timeout: 超时时间，单位秒

    Returns:
        标准化的响应字典（见模块文档）
    """
    try:
        # 构建请求参数
        kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": headers or {},
            "timeout": timeout,
        }
        if body is not None:
            kwargs["json"] = body  # 自动序列化为 JSON 并设置 Content-Type

        # 发送请求
        resp = requests.request(**kwargs)
        elapsed_ms = round(resp.elapsed.total_seconds() * 1000, 2)

        # 尝试解析 JSON 响应，失败则返回原始文本
        try:
            body_json = resp.json()
        except Exception:
            body_json = resp.text

        return {
            "status_code": resp.status_code,
            "body": body_json,
            "headers": dict(resp.headers),
            "elapsed_ms": elapsed_ms,
            "error": None,
        }

    # 以下异常不会向上抛出，而是记录在 error 字段中
    except requests.exceptions.Timeout as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Timeout: {e}"}
    except requests.exceptions.ConnectionError as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"ConnectionError: {e}"}
    except Exception as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Error: {e}"}
