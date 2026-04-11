from typing import Any

import requests


def send_request(
    method: str,
    url: str,
    headers: dict = None,
    body: dict = None,
    timeout: int = 30,
) -> dict[str, Any]:
    try:
        kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": headers or {},
            "timeout": timeout,
        }
        if body is not None:
            kwargs["json"] = body

        resp = requests.request(**kwargs)
        elapsed_ms = round(resp.elapsed.total_seconds() * 1000, 2)

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

    except requests.exceptions.Timeout as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Timeout: {e}"}
    except requests.exceptions.ConnectionError as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"ConnectionError: {e}"}
    except Exception as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Error: {e}"}
