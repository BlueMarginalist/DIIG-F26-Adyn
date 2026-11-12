"""All analysis settings in one place.

Every value here was hard-coded in the original scripts (funnel_v2.py, next_analysis.py,
fix_queries.py, diag*.py). They are collected so the company can change them for production
data without editing any SQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class Config:
    # --- connection -------------------------------------------------------------
    env_prefix: str = "ADYN_POSTGRES"      # reads <PREFIX>_HOST / _PORT / _DB / _USER / _PASSWORD
    connect_timeout: int = 10

    # --- who counts as a customer ---------------------------------------------------
    replacement_pattern: str = "%replacement%"  # orders.name ILIKE this => replacement order
    bulk_account_min_orders: int = 10           # accounts with this many orders or more are excluded
    customer_roles: Tuple[int, ...] = (2, 3)    # 2 customer, 3 purchaser
    staff_roles: Tuple[int, ...] = (0, 1, 5)    # 0 admin, 1 editor, 5 physician

    # --- order status names (underscores are normalised to spaces in SQL) ----------------
    reserved_status: str = "reserved"
    sent_to_allied_status: str = "allied reserved"
    shipped_status: str = "left allied facility"

    # --- dates -------------------------------------------------------------------------
    # Timing is only measured for orders paid on/after this date. In staging, older orders had
    # bulk-stamped shipping/lab dates. Set to None-like '1900-01-01' on production if dates are clean.
    timing_since: str = "2023-01-01"

    # --- test / internal account heuristics ---------------------------------------------
    test_email_patterns: Tuple[str, ...] = ("%test%", "%+%", "%example.%", "%mailinator%")
    test_name_pattern: str = "%test%"
    shared_ip_min_orders: int = 5
    domain_min_buyers: int = 5

    # --- replacement reasons (shipments_replacements.reason) ------------------------------
    reason_min_count: int = 2
    placeholder_like_pattern: str = "%test%"
    placeholder_reasons: Tuple[str, ...] = ("some reason", "reason", "new reason", "reason for replacement")
    structured_reason_prefixes: Tuple[str, ...] = ("Lab reported%", "Mail:%", "Customer reported%")

    # --- reporting ----------------------------------------------------------------------------
    small_n: int = 20                           # groups smaller than this are flagged small_n
    top_states: int = 8
    age_bins: Tuple[int, ...] = (0, 24, 29, 34, 200)
    age_labels: Tuple[str, ...] = ("<=24", "25-29", "30-34", "35+")

    def params(self) -> dict:
        """Named parameters passed to every query (psycopg2 %(name)s style)."""
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
        }
