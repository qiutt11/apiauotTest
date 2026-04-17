"""变量池模块。

管理测试过程中的变量存储和解析，支持三层优先级：
    临时变量 (temp)   > 模块变量 (module)  > 全局变量 (global)

变量来源：
    - 全局变量：config/{env}.yaml 中的 global_variables
    - 模块变量：用例 extract / db_setup extract / db_extract 提取的值
    - 临时变量：用例级别覆盖（预留）

使用 ${变量名} 语法在用例的任意字符串字段中引用变量。
当 ${var} 是字段的完整值时，保留原始类型（int、bool 等）；
嵌入在字符串中时（如 "Bearer ${token}"），转为字符串。
"""

import re
from typing import Any

from loguru import logger


class VariablePool:
    """三层优先级变量池。"""

    def __init__(self):
        self._global: dict[str, Any] = {}   # 全局变量（来自 config）
        self._module: dict[str, Any] = {}   # 模块变量（来自 extract，文件切换时清空）
        self._temp: dict[str, Any] = {}     # 临时变量（用例级覆盖）

    def set_global(self, key: str, value: Any):
        """设置全局变量（最低优先级）。"""
        self._global[key] = value

    def set_module(self, key: str, value: Any):
        """设置模块变量（中等优先级，同一 YAML 文件内共享）。"""
        self._module[key] = value

    def set_temp(self, key: str, value: Any):
        """设置临时变量（最高优先级）。"""
        self._temp[key] = value

    def get(self, key: str) -> Any:
        """按优先级查找变量：temp > module > global。未找到返回 None。"""
        if key in self._temp:
            return self._temp[key]
        if key in self._module:
            return self._module[key]
        if key in self._global:
            return self._global[key]
        return None

    def resolve(self, data: Any) -> Any:
        """递归解析数据中的 ${变量名} 引用。

        支持 str、dict、list 类型的递归解析。
        其他类型（int、bool、None 等）原样返回。
        """
        if isinstance(data, str):
            return self._resolve_string(data)
        if isinstance(data, dict):
            return {k: self.resolve(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.resolve(item) for item in data]
        return data

    def _resolve_string(self, text: str) -> Any:
        """解析字符串中的 ${变量名}。

        - 完整匹配（如 "${user_id}"）：返回变量的原始类型（int 42 而非 str "42"）
        - 部分匹配（如 "Bearer ${token}"）：替换为字符串，返回 str
        - 未找到的变量：保留原文 ${xxx} 并输出 warning 日志
        """
        # 情况 1：整个字符串就是一个变量引用 → 返回原始类型
        single_match = re.fullmatch(r'\$\{(\w+)}', text)
        if single_match:
            var_name = single_match.group(1)
            value = self.get(var_name)
            if value is not None:
                return value
            logger.warning(f"Unresolved variable: ${{{var_name}}}")
            return text

        # 情况 2：字符串中嵌入了变量 → 替换为字符串
        def replacer(match):
            key = match.group(1)
            value = self.get(key)
            if value is None:
                logger.warning(f"Unresolved variable: ${{{key}}}")
                return match.group(0)  # 保留原文
            return str(value)
        return re.sub(r'\$\{(\w+)}', replacer, text)

    def clear_temp(self):
        """清空临时变量。"""
        self._temp.clear()

    def clear_module(self):
        """清空模块变量（在切换 YAML 文件时调用，实现文件间变量隔离）。"""
        self._module.clear()
