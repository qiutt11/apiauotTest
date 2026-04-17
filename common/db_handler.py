"""数据库操作模块。

提供测试用例中数据库相关操作的支持：
    - execute_setup():    前置数据准备（INSERT/UPDATE），支持 extract 提取变量
    - execute_extract():  请求后查询数据库校验（SELECT + extract）
    - execute_teardown(): 测试后清理数据（DELETE）

特性：
    - 参数化查询（防 SQL 注入）：sql + params
    - 自动重连：每次操作前 ping 检测
    - 事务安全：失败时自动 rollback
    - 安全关闭：防止 double-close

示例 YAML 用法：
    db_setup:
      - sql: "INSERT INTO users (phone, name) VALUES (%s, %s)"
        params: ["13800001111", "test"]
      - sql: "SELECT id FROM users WHERE phone = %s"
        params: ["13800001111"]
        extract:
          user_id: id
"""

from typing import Any

import pymysql
from pymysql.cursors import DictCursor


class DBHandler:
    """MySQL 数据库操作处理器。"""

    def __init__(self, config: dict):
        """创建数据库连接。

        Args:
            config: 数据库配置字典，包含 host, port, user, password, database, charset
        """
        self._conn = pymysql.connect(
            host=config["host"],
            port=config.get("port", 3306),
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config.get("charset", "utf8mb4"),
            cursorclass=DictCursor,  # 查询结果返回 dict 而非 tuple
        )

    def _ensure_connection(self):
        """确保数据库连接可用，断开时自动重连。"""
        if self._conn is None:
            raise RuntimeError("DBHandler has been closed")
        self._conn.ping(reconnect=True)

    def execute_setup(self, sql_list: list[dict]) -> dict[str, Any]:
        """执行前置 SQL 列表（支持 extract 提取变量）。

        每条 SQL 可选 params（参数化防注入）和 extract（提取查询结果为变量）。
        如果执行中途失败，已执行的 SQL 会自动 rollback。

        Args:
            sql_list: SQL 列表，每项格式：
                {"sql": "SELECT ...", "params": [...], "extract": {"变量名": "列名"}}

        Returns:
            提取到的变量字典（无 extract 时返回空 dict）
        """
        self._ensure_connection()
        extracted = {}
        try:
            with self._conn.cursor() as cursor:
                for item in sql_list:
                    cursor.execute(item["sql"], item.get("params"))
                    # 如果这条 SQL 需要提取结果（通常是 SELECT）
                    if item.get("extract"):
                        row = cursor.fetchone()
                        for var_name, column_name in item["extract"].items():
                            extracted[var_name] = row[column_name] if row else None
            self._conn.commit()
        except Exception:
            self._conn.rollback()  # 失败时回滚，防止脏数据
            raise
        return extracted

    def execute_teardown(self, sql_list: list[dict]):
        """执行清理 SQL 列表（通常是 DELETE）。

        Args:
            sql_list: SQL 列表，每项格式：{"sql": "DELETE ...", "params": [...]}
        """
        self._ensure_connection()
        try:
            with self._conn.cursor() as cursor:
                for item in sql_list:
                    cursor.execute(item["sql"], item.get("params"))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute_extract(self, extract_list: list[dict]) -> dict[str, Any]:
        """执行查询 SQL 并提取变量（用于请求后的数据库校验）。

        Args:
            extract_list: 查询列表，每项格式：
                {"sql": "SELECT ...", "params": [...], "extract": {"变量名": "列名"}}

        Returns:
            提取到的变量字典
        """
        self._ensure_connection()
        result = {}
        with self._conn.cursor() as cursor:
            for item in extract_list:
                cursor.execute(item["sql"], item.get("params"))
                row = cursor.fetchone()
                for var_name, column_name in item["extract"].items():
                    result[var_name] = row[column_name] if row else None
        return result

    def close(self):
        """关闭数据库连接（防止 double-close）。"""
        if self._conn:
            self._conn.close()
            self._conn = None  # 标记为已关闭，防止重复 close
