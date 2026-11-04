"""Cached retrieval, following Shihyun's AdynData pattern.

Each property runs its query once and keeps the result; call refresh() to query again. Nothing here
cleans or analyses; that lives in clean.py and analysis.py.
"""
from functools import cached_property

from . import queries
from .config import Config


def _table(sql):
    """A cached property that runs `sql` (with the config's named parameters) and returns a DataFrame."""
    @cached_property
    def prop(self):
        return self._run(sql)
    return prop


class FunnelData:
    def __init__(self, db, cfg=None):
        self.db = db
        self.cfg = cfg or Config()
        self._cohorts = {}

    def _run(self, sql, **extra):
        params = {**self.cfg.params(), **extra}
        return self.db.query(sql, params if "%(" in sql else None)

    def refresh(self):
        for klass in type(self).__mro__:
            for name, value in vars(klass).items():
                if isinstance(value, cached_property):
                    self.__dict__.pop(name, None)
        self._cohorts = {}

    # --- customer-level funnel (one row per account, before cleaning)
    customers_raw = _table(queries.CUSTOMER_FUNNEL)
    kit_outcomes = _table(queries.KIT_OUTCOMES)
    sample_status_by_kind = _table(queries.SAMPLE_STATUS_BY_KIND)

    # --- test / internal accounts
    test_like_accounts = _table(queries.TEST_LIKE_ACCOUNTS)
    email_domains = _table(queries.EMAIL_DOMAINS)
    shared_ips = _table(queries.SHARED_IPS)
    staff_roles = _table(queries.STAFF_ROLES)
    paid_vs_unpaid = _table(queries.PAID_VS_UNPAID)
    order_status_totals = _table(queries.ORDER_STATUS_TOTALS)

    # --- replacement kits
    replacements_per_customer = _table(queries.REP_PER_CUSTOMER)
    replacement_reasons = _table(queries.REP_REASONS)
    replacement_reason_counts = _table(queries.REP_REASON_CLASSES)
    replacement_totals = _table(queries.REP_TOTALS)
    replaced_sample_status = _table(queries.REP_ORIGINAL_SAMPLE_STATUS)
    replacements_by_product = _table(queries.REP_BY_PRODUCT)
    replacements_by_month = _table(queries.REP_BY_MONTH)
    replacement_vs_viewing = _table(queries.REP_VS_VIEWING)

    # --- time between steps
    paid_to_shipped = _table(queries.PAID_TO_SHIPPED)
    shipped_to_lab = _table(queries.SHIPPED_TO_LAB)
    lab_to_result = _table(queries.LAB_TO_RESULT)
    result_to_approved = _table(queries.RESULT_TO_APPROVED)
    return_timing = _table(queries.RETURN_TIMING)

    # --- blocking steps between payment and shipping
    furthest_step = _table(queries.FURTHEST_STEP)
    profile_sequence = _table(queries.PROFILE_SEQUENCE)
    profile_days = _table(queries.PROFILE_DAYS)
    optional_forms = _table(queries.OPTIONAL_FORMS)
    steps_by_year = _table(queries.STEPS_BY_YEAR)
    medical_biography = _table(queries.MEDBIO)

    # --- date quality
    date_sanity = _table(queries.DATE_SANITY)

    @cached_property
    def date_quality(self):
        """Per date column: how many dates fall on the single busiest day (bulk-stamping shows up as a high share)."""
        import pandas as pd
        parts = []
        for table, column in queries.DATE_COLUMNS:
            try:
                parts.append(self._run(queries.date_quality_sql(table, column)))
            except Exception as error:  # a column may not exist in another environment
                parts.append(pd.DataFrame([{"table_name": table, "column_name": column,
                                            "error": str(error).splitlines()[0][:80]}]))
        return pd.concat(parts, ignore_index=True)

    def cohort_by_month(self, start="2023-01-01", end="2024-01-01"):
        """Paid, profile-complete and shipped orders by month paid, within [start, end)."""
        key = (start, end)
        if key not in self._cohorts:
            self._cohorts[key] = self._run(queries.COHORT_BY_MONTH, cohort_start=start, cohort_end=end)
        return self._cohorts[key]

    def run_diagnostics(self, group="diagnostics"):
        """Run the named exploration queries ('profile' or 'diagnostics'); a failing query returns its error text."""
        qs = queries.PROFILE if group == "profile" else queries.DIAGNOSTICS
        out = {}
        for name, sql in qs.items():
            try:
                out[name] = self._run(sql)
            except Exception as error:  # noqa: BLE001
                out[name] = f"ERROR: {str(error).splitlines()[0]}"
        return out
