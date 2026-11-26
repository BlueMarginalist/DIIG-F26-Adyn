"""Shared table-contract checks; input tables are not modified."""


def require_columns(data, columns):
    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(f"Required columns missing: {', '.join(sorted(missing))}")
