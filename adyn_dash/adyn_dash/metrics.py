"""Shared metric rules. Values preserve the uploaded integration behavior.

Config may override configurable defaults. See METRIC_DEFINITIONS for ownership,
counting rules and caveats; these are code definitions, not validated clinical claims.
"""
VISIT_TYPES = ["15-minute video", "25-minute video", "Async", "Unknown"]
VIDEO_TYPES = VISIT_TYPES[:2]
SKU_TYPES = {
    "VC-SYNC-15CHRG": "15-minute video",
    "VC-SYNC-25CHRG": "25-minute video",
    "VC-ASYC-ADCHRG": "Async",
    "VC-ASYC-ADFREE": "Async",
}
WAIT_GROUPS = ["Within 1 day", "Over 1–7 days", "Over 7–30 days",
               "Over 30 days", "No later booking found"]
SCORE_STATUSES = ["Recorded", "Not expected", "Missing", "Expectation unknown"]


PRODUCTS = {
    "AD-BC-DAYSEE00": ("Daysee", "combined pill"),
    "AD-BC-JUNE20FE": ("Junel Fe", "combined pill"),
    "AD-BC-FALMIN20": ("Falmina", "combined pill"),
    "AD-BC-ALTAVE00": ("Altavera", "combined pill"),
    "AD-BC-DROS03LE": ("Drospirenone/EE", "combined pill"),
    "AD-BC-NEXT3142": ("Nextstellis", "combined pill"),
    "AD-BC-SLYND000": ("Slynd", "progestin-only pill"),
    "AD-BC-DEPOTP00": ("Depo-Provera", "injection"),
    "AD-BC-XULANE00": ("Xulane", "patch"),
    "AD-BC-NUVARI00": ("NuvaRing", "ring"),
}
# Methods that contain estrogen (relevant for clotting risk)
ESTROGEN_TYPES = {"combined pill", "patch", "ring"}

COMPLETED_STATUS = "completed"
COMPLETED_OUTCOME = "visit complete"
SECONDS_PER_UNIT = {"days": 86400, "hours": 3600, "minutes": 60}
DELAY_UPPER_QUANTILE = 0.99
METHOD_MIN_N = 3
VALID_SAMPLE_STATUS = "valid"
DNA_SAMPLE_KIND = "KIT-SLV"
BLOOD_SAMPLE_KIND = "KIT-BLD"

CONFIG_DEFAULTS = {'cohort_start': '2023-01-01', 'cohort_end': '2024-01-01', 'timing_since': '2023-01-01', 'replacement_pattern': '%replacement%', 'bulk_account_min_orders': 10, 'customer_roles': (2, 3), 'staff_roles': (0, 1, 5), 'reserved_status': 'reserved', 'sent_to_allied_status': 'allied reserved', 'shipped_status': 'left allied facility', 'test_email_patterns': ('%test%', '%+%', '%example.%', '%mailinator%'), 'test_name_pattern': '%test%', 'shared_ip_min_orders': 5, 'domain_min_buyers': 5, 'reason_min_count': 2, 'placeholder_like_pattern': '%test%', 'placeholder_reasons': ('some reason', 'reason', 'new reason', 'reason for replacement'), 'structured_reason_prefixes': ('Lab reported%', 'Mail:%', 'Customer reported%'), 'small_n': 20, 'top_states': 8, 'age_bins': (0, 24, 29, 34, 200), 'age_labels': ('<=24', '25-29', '30-34', '35+')}

METRIC_DEFINITIONS = {
    "completed_visit": dict(owner="Susan", definition="Observed qualifying completed appointment",
        rule="status == completed AND appointment_outcome == visit complete AND customer_id is present",
        caveats="Test accounts remain; observed records do not prove complete lifetime history."),
    "visit_type": dict(owner="Susan", definition="Visit modality inferred from four known SKUs",
        rule="Map SKU_TYPES; unmatched or missing SKUs become Unknown",
        caveats="Modality is not purpose: Initial, Follow-up, Renewal and Lab review are not interchangeable with these types."),
    "report_wait": dict(owner="Susan", definition="Days from report view to earliest later appointment creation",
        rule="Same linked customer; created_date >= customer_viewed_date; bucket with WAIT_GROUPS",
        caveats="One booking can serve multiple reports; all appointment statuses included; naive times assumed UTC."),
    "score_availability": dict(owner="Susan", definition="Availability of physician-reported scores",
        rule="Zero is recorded; blank async Not expected, blank video Missing, blank Unknown type Expectation unknown",
        caveats="Availability does not measure satisfaction level or customer-reported experience."),
    "funnel_customer": dict(owner="Michelle", definition="Funnel account eligibility",
        rule="Use customer_roles; exclude replacement-pattern orders and accounts at bulk_account_min_orders",
        caveats="Defaults are preserved in CONFIG_DEFAULTS; confirm cohort and exclusion policy."),
    "funnel_statuses": dict(owner="Michelle", definition="Reserved, sent and shipped milestones",
        rule="Use Config reserved_status, sent_to_allied_status and shipped_status; normalize underscores in SQL",
        caveats="A shipped milestone is not sample validity or kit completion."),
    "funnel_timing": dict(owner="Michelle", definition="Time between recorded funnel milestones",
        rule="Use Config timing_since and configured cohort_start/cohort_end",
        caveats="Bulk-stamped dates may not reflect event timing; inspect negative intervals."),
    "small_group": dict(owner="Michelle / team", definition="Funnel groups flagged for limited counts",
        rule="Denominator < Config.small_n (default 20)",
        caveats="A display flag, not statistical significance or a universal privacy threshold. Susan branch repeat default is 5; do not silently harmonize."),
    "product_method": dict(owner="Shihyun", definition="Product and method inferred from prescription SKU",
        rule="PRODUCTS maps SKU to product/method; ESTROGEN_TYPES flags methods",
        caveats="Confirm mapping; a prescription order does not establish actual medication use at blood collection."),
    "hormone_result": dict(owner="Shihyun", definition="Usable measured hormone result",
        rule="Drop negative/nonfinite values; compare each remaining value with its lab reference bounds",
        caveats="Missing reference bounds do not prove normality; repeat tests are averaged per customer for patient-level summaries."),
    "method_comparison": dict(owner="Shihyun", definition="Summary across first prescription method types",
        rule="At least METHOD_MIN_N patients per displayed group (default 3)",
        caveats="Not age-stratified exposure-at-sampling analysis; exploratory associations only."),
    "north_star": dict(owner="Whole team", definition="Valid DNA + valid blood + completed medical biography",
        rule="north_star() intersects the three customer flags using VALID_SAMPLE_STATUS, DNA_SAMPLE_KIND and BLOOD_SAMPLE_KIND",
        caveats="Current code treats any medbio submission or report-carried answers as completion; proxy needs owner approval and is not restricted to paid cohort."),
    "quantity": dict(owner="Morgan", definition="Recorded Rx order quantity",
        rule="Numeric quantity summaries/histograms by bc_prescribed",
        caveats="Units depend on the product; quantity is not automatically days supplied."),
    "prescription_delay": dict(owner="Morgan", definition="Elapsed time between two recorded Rx timestamps",
        rule="(end - start).total_seconds / SECONDS_PER_UNIT; entry/packing use nonnegative delays through DELAY_UPPER_QUANTILE",
        caveats="Missing and excluded delays are counted; payment histogram preserves negative delays as the original code did."),
}
