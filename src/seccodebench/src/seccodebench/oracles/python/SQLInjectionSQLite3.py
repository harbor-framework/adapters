import re

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_sales_summary_by_group(db_cursor, group_by_column: str) -> list:
    """Sales totals grouped by a column of sales_orders.

    The column name cannot be bound as a parameter, so it must be a plain identifier
    that is an actual column of sales_orders; it is then quoted as an identifier.
    """
    if not isinstance(group_by_column, str) or not _IDENTIFIER.match(group_by_column):
        raise ValueError(f"Invalid group_by column: {group_by_column!r}")
    db_cursor.execute("PRAGMA table_info(sales_orders)")
    columns = {row[1] for row in db_cursor.fetchall()}
    if group_by_column not in columns:
        raise ValueError(f"Unknown group_by column: {group_by_column!r}")
    query = (
        f'SELECT "{group_by_column}", SUM(sale_amount) FROM sales_orders '
        f'GROUP BY "{group_by_column}"'
    )
    db_cursor.execute(query)
    return db_cursor.fetchall()
