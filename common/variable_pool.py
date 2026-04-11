import re
from typing import Any

from loguru import logger


class VariablePool:
    def __init__(self):
        self._global: dict[str, Any] = {}
        self._module: dict[str, Any] = {}
        self._temp: dict[str, Any] = {}

    def set_global(self, key: str, value: Any):
        self._global[key] = value

    def set_module(self, key: str, value: Any):
        self._module[key] = value

    def set_temp(self, key: str, value: Any):
        self._temp[key] = value

    def get(self, key: str) -> Any:
        if key in self._temp:
            return self._temp[key]
        if key in self._module:
            return self._module[key]
        if key in self._global:
            return self._global[key]
        return None

    def resolve(self, data: Any) -> Any:
        if isinstance(data, str):
            return self._resolve_string(data)
        if isinstance(data, dict):
            return {k: self.resolve(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.resolve(item) for item in data]
        return data

    def _resolve_string(self, text: str) -> Any:
        # If the entire string is a single ${var}, return the typed value
        single_match = re.fullmatch(r'\$\{(\w+)}', text)
        if single_match:
            var_name = single_match.group(1)
            value = self.get(var_name)
            if value is not None:
                return value
            logger.warning(f"Unresolved variable: ${{{var_name}}}")
            return text

        # Otherwise do string interpolation (always returns str)
        def replacer(match):
            key = match.group(1)
            value = self.get(key)
            if value is None:
                logger.warning(f"Unresolved variable: ${{{key}}}")
                return match.group(0)
            return str(value)
        return re.sub(r'\$\{(\w+)}', replacer, text)

    def clear_temp(self):
        self._temp.clear()

    def clear_module(self):
        self._module.clear()
