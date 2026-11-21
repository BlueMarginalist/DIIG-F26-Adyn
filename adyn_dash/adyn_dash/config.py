"""All settings in one place: connection, thresholds and patterns.

Every value that used to be hard-coded in an analyst's scripts lives here, so a client can adapt the
dashboard to production data by changing configuration instead of code. The funnel thresholds come from
Michelle Zuo's Config; the connection variables follow the ADYN_POSTGRES_* convention shared by everyone.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from .metrics import CONFIG_DEFAULTS
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class Config:
    # --- connection -------------------------------------------------------------
    env_prefix: str = "ADYN_POSTGRES"      # reads <PREFIX>_HOST / _PORT / _DB / _USER / _PASSWORD
    connect_timeout: int = 10
    database_schema: Optional[str] = None  # or <prefix>_SCHEMA; database default when unset
    sql_override_dir: Optional[str] = None  # a folder of .sql files that replaces the bundled queries

    # --- privacy guard ----------------------------------------------------------------
    max_output_rows: int = 5000            # a chart table longer than this is probably row-level data
    forbidden_columns: Tuple[str, ...] = ("customer_id", "patient_id", "email", "first_name", "last_name",
                                          "phone", "ip", "date_of_birth", "customer_dob", "password_hash")

    # --- reporting windows --------------------------------------------------------------
    as_of: Optional[str] = None            # date used for ages (None = today)
    cohort_start: str = CONFIG_DEFAULTS['cohort_start']       # funnel cohort chart: [start, end)
    cohort_end: str = CONFIG_DEFAULTS['cohort_end']
    timing_since: str = CONFIG_DEFAULTS['timing_since']       # timing is measured only for orders paid on/after this date

    # --- funnel: who counts as a customer ----------------------------------------------------
    replacement_pattern: str = CONFIG_DEFAULTS['replacement_pattern']  # orders.name ILIKE this => replacement order
    bulk_account_min_orders: int = CONFIG_DEFAULTS['bulk_account_min_orders']           # accounts with this many orders or more are excluded
    customer_roles: Tuple[int, ...] = CONFIG_DEFAULTS['customer_roles']    # 2 customer, 3 purchaser
    staff_roles: Tuple[int, ...] = CONFIG_DEFAULTS['staff_roles']    # 0 admin, 1 editor, 5 physician

    # --- funnel: order status names (underscores are normalised to spaces in SQL) -----------------
    reserved_status: str = CONFIG_DEFAULTS['reserved_status']
    sent_to_allied_status: str = CONFIG_DEFAULTS['sent_to_allied_status']
    shipped_status: str = CONFIG_DEFAULTS['shipped_status']

    # --- funnel: test / internal account heuristics -----------------------------------------------
    test_email_patterns: Tuple[str, ...] = CONFIG_DEFAULTS['test_email_patterns']
    test_name_pattern: str = CONFIG_DEFAULTS['test_name_pattern']
    shared_ip_min_orders: int = CONFIG_DEFAULTS['shared_ip_min_orders']
    domain_min_buyers: int = CONFIG_DEFAULTS['domain_min_buyers']

    # --- funnel: replacement reasons (shipments_replacements.reason) ------------------------------
    reason_min_count: int = CONFIG_DEFAULTS['reason_min_count']
    placeholder_like_pattern: str = CONFIG_DEFAULTS['placeholder_like_pattern']
    placeholder_reasons: Tuple[str, ...] = CONFIG_DEFAULTS['placeholder_reasons']
    structured_reason_prefixes: Tuple[str, ...] = CONFIG_DEFAULTS['structured_reason_prefixes']

    # --- funnel: grouping --------------------------------------------------------------------------
    small_n: int = CONFIG_DEFAULTS['small_n']                           # groups smaller than this are flagged small_n
    top_states: int = CONFIG_DEFAULTS['top_states']
    age_bins: Tuple[int, ...] = CONFIG_DEFAULTS['age_bins']
    age_labels: Tuple[str, ...] = CONFIG_DEFAULTS['age_labels']

    def __post_init__(self):
        if self.connect_timeout <= 0 or self.small_n <= 0:
            raise ValueError("Timeout and small-group threshold must be positive")

    @property
    def connection_schema(self):
        return self.database_schema or os.getenv(f"{self.env_prefix}_SCHEMA")

    @property
    def sql_dir(self) -> Path:
        return Path(__file__).resolve().parent / "sources"

    def params(self) -> dict:
        """Named parameters passed to every query that uses them (psycopg %(name)s style)."""
        return {
            "replacement_pattern": self.replacement_pattern,
            "bulk_min": self.bulk_account_min_orders,
            "customer_roles": list(self.customer_roles),
            "staff_roles": list(self.staff_roles),
            "reserved_status": self.reserved_status,
            "sent_to_allied_status": self.sent_to_allied_status,
            "shipped_status": self.shipped_status,
            "timing_since": self.timing_since,
            "test_email_patterns": list(self.test_email_patterns),
            "test_name_pattern": self.test_name_pattern,
            "shared_ip_min": self.shared_ip_min_orders,
            "domain_min": self.domain_min_buyers,
            "reason_min_count": self.reason_min_count,
            "placeholder_like_pattern": self.placeholder_like_pattern,
            "placeholder_reasons": list(self.placeholder_reasons),
            "structured_prefixes": list(self.structured_reason_prefixes),
            "cohort_start": self.cohort_start,
            "cohort_end": self.cohort_end,
        }
