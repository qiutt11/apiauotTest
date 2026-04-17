from typing import Any

import pymysql
from pymysql.cursors import DictCursor


class DBHandler:
    def __init__(self, config: dict):
        self._conn = pymysql.connect(
            host=config["host"],
            port=config.get("port", 3306),
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config.get("charset", "utf8mb4"),
            cursorclass=DictCursor,
        )

    def _ensure_connection(self):
        """Reconnect if the connection has been lost."""
        if self._conn is None:
            raise RuntimeError("DBHandler has been closed")
        self._conn.ping(reconnect=True)

    def execute_setup(self, sql_list: list[dict]) -> dict[str, Any]:
        """Execute setup SQLs. Returns extracted variables from SQLs that have 'extract'.

        Each SQL item can optionally have an 'extract' dict to capture query results.
        This allows earlier SQLs to generate data that later SQLs reference.
        """
        self._ensure_connection()
        extracted = {}
        try:
            with self._conn.cursor() as cursor:
                for item in sql_list:
                    cursor.execute(item["sql"], item.get("params"))
                    if item.get("extract"):
                        row = cursor.fetchone()
                        for var_name, column_name in item["extract"].items():
                            extracted[var_name] = row[column_name] if row else None
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return extracted

    def execute_teardown(self, sql_list: list[dict]):
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
        if self._conn:
            self._conn.close()
            self._conn = None
