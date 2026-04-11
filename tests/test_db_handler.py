from unittest.mock import patch, MagicMock

from common.db_handler import DBHandler


def _make_db_config():
    return {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "123456",
        "database": "test_db",
        "charset": "utf8mb4",
    }


def _setup_mock_cursor(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # cursor() is used as context manager: `with conn.cursor() as cursor:`
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn
    return mock_conn, mock_cursor


@patch("common.db_handler.pymysql.connect")
def test_execute_setup_sql(mock_connect):
    mock_conn, mock_cursor = _setup_mock_cursor(mock_connect)

    handler = DBHandler(_make_db_config())
    handler.execute_setup([
        {"sql": "INSERT INTO users (id, name) VALUES (1, 'test')"},
        {"sql": "INSERT INTO roles (id, name) VALUES (1, 'admin')"},
    ])

    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called()
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_teardown_sql(mock_connect):
    mock_conn, mock_cursor = _setup_mock_cursor(mock_connect)

    handler = DBHandler(_make_db_config())
    handler.execute_teardown([
        {"sql": "DELETE FROM users WHERE id = 1"},
    ])

    mock_cursor.execute.assert_called_once_with("DELETE FROM users WHERE id = 1")
    mock_conn.commit.assert_called()
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_extract(mock_connect):
    mock_conn, mock_cursor = _setup_mock_cursor(mock_connect)
    mock_cursor.fetchone.return_value = {"status": "pending", "total_price": 99.9}

    handler = DBHandler(_make_db_config())
    result = handler.execute_extract([
        {
            "sql": "SELECT status, total_price FROM orders WHERE id = 1",
            "extract": {"db_status": "status", "db_price": "total_price"},
        }
    ])

    assert result == {"db_status": "pending", "db_price": 99.9}
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_extract_no_result(mock_connect):
    mock_conn, mock_cursor = _setup_mock_cursor(mock_connect)
    mock_cursor.fetchone.return_value = None

    handler = DBHandler(_make_db_config())
    result = handler.execute_extract([
        {
            "sql": "SELECT status FROM orders WHERE id = 999",
            "extract": {"db_status": "status"},
        }
    ])

    assert result == {"db_status": None}
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_close_connection(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    handler.close()

    mock_conn.close.assert_called_once()
