"""
Example hook functions.

Hook functions receive a dict and must return a dict.
- before hooks receive: {"method": str, "url": str, "headers": dict, "body": dict}
- after hooks receive: {"status_code": int, "body": dict, "headers": dict, "elapsed_ms": float, "error": None}

Usage in test case YAML:
  hook:
    before: my_before_function
    after: my_after_function
"""


def example_add_timestamp(request_data):
    """Example: add timestamp to request body before sending."""
    import time
    if request_data.get("body") and isinstance(request_data["body"], dict):
        request_data["body"]["_timestamp"] = int(time.time())
    return request_data
