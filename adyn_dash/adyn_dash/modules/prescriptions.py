"""Prescription journey: orders, quantities, fulfilment delays and shipping. Analyses by Morgan Kay (morgan branch).

The computations live in lib/prescriptions/calc.py (functions taken from Morgan's package.ipynb, with the
plotting and table-loading code removed). This class asks for the sources, aggregates each result and
attaches the chart spec. Nothing here returns person-level rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..lib.prescriptions import calc
from ..module import AnalysisModule, chart
from ..source import Source

ORDER_COLUMNS = ("id", "customer_id", "date_order_placed", "date_order_paid", "sku", "bc_prescribed",
                 "quantity", "refills_allowed", "status", "customer_approved", "adyn_approved", "suspended")
APPROVAL_FLAGS = {"customer_approved": "Customer approved", "adyn_approved": "Adyn approved",
                  "suspended": "Suspended"}


class Prescriptions(AnalysisModule):
    name = "prescriptions"
    title = "Prescription journey"
    owner = "Morgan Kay"
    sources = (
        Source("prescriptions", "rx_orders", ORDER_COLUMNS),
        Source("prescriptions", "rx_written", ("patient_id", "ndc", "customer_dob", "rx_written_date_time",
                                               "rx_creation_date_time")),
        Source("prescriptions", "rx_shipments", ("rx_order_id", "state")),
        Source("prescriptions", "rx_packed", ("id", "order_receipt_date_time", "packed_date_time")),
        Source("prescriptions", "rx_matches", ("rx_order_id", "rx_packed_id")),
    )
    assumptions = (
        "Delays that are negative (end before start) are excluded from delay charts and counted separately.",
        "Entry and packing delays are shown through the 99th percentile to keep outliers from hiding the shape.",
        "Ages use the date set in Config.as_of (today by default); conflicting dates of birth stop the chart.",
        "Missing categories get their own bar instead of being dropped.",
    )

    # ---- orders -------------------------------------------------------------------------------------
    @chart("Orders placed per month", "bar", x="month", y="n_records",
           note="Includes months with zero orders inside the date range.")
    def orders_by_month(self):
        return calc.monthly_counts(self.data("rx_orders"), "date_order_placed")

    @chart("Orders by status", "bar", x="status", y="n_orders")
    def order_status(self):
        return calc.order_status_summary(self.data("rx_orders"))

    @chart("Approval and suspension flags", "bar", x="flag", y="n_orders", color="value", stack=True,
           note="Counts of true, false and missing values for each flag.")
    def approval_flags(self):
        return calc.flag_counts(self.data("rx_orders"), APPROVAL_FLAGS)

    @chart("Orders by product (SKU)", "bar", x="sku", y="n_records")
    def orders_by_sku(self):
        return calc.category_counts(self.data("rx_orders"), "sku")

    @chart("Orders by birth-control flag", "bar", x="bc_prescribed", y="n_records")
    def orders_by_bc(self):
        return calc.category_counts(self.data("rx_orders"), "bc_prescribed")

    @chart("Refills allowed per order", "bar", x="refills_allowed", y="n_records")
    def refills_allowed(self):
        return calc.category_counts(self.data("rx_orders"), "refills_allowed")

    @chart("Quantity prescribed", "bar", x="bin_start", y="orders", color="group", filters=("group",),
           note="Split by birth-control flag; shared bin edges.")
    def quantity_distribution(self):
        d = self.data("rx_orders")
        return calc.value_histogram(d["quantity"], bins=20, by=d["bc_prescribed"])

    @chart("Quantity summary by birth-control flag", "table", note="Count, mean, median and spread of quantity.")
    def quantity_by_bc(self):
        return calc.quantity_summary(self.data("rx_orders"), "bc_prescribed")

    @chart("Customers who ordered more than once", "bar", x="group", y="customers")
    def repeat_customers(self):
        return calc.repeat_customer_counts(calc.repeat_order_summary(self.data("rx_orders")))

    # ---- patients ---------------------------------------------------------------------------------------
    @chart("Prescriptions written per patient", "bar", x="n_prescriptions", y="patients")
    def prescriptions_per_patient(self):
        per = calc.prescriptions_per_patient(self.data("rx_written"))
        return calc.prescription_count_distribution(per)

    @chart("Age of customers", "bar", x="age_group", y="patients",
           note="One record per patient, five-year bands. Future dates of birth are shown separately.")
    def customer_age(self):
        ages = calc.customer_ages(self.data("rx_written"), as_of=self.cfg.as_of)
        return calc.age_groups(ages).drop(columns="start")

    # ---- delays ------------------------------------------------------------------------------------------
    @chart("Time from prescription writing to entry (hours)", "bar", x="bin_start", y="orders",
           note="Non-negative delays up to the 99th percentile.")
    def entry_delay(self):
        return calc.delay_histogram(self.data("rx_written"), "rx_written_date_time", "rx_creation_date_time",
                                    unit="hours", nonnegative=True, upper_quantile=0.99)

    @chart("Time from order receipt to packing (minutes)", "bar", x="bin_start", y="orders",
           note="Non-negative delays up to the 99th percentile.")
    def packing_delay(self):
        return calc.delay_histogram(self.data("rx_packed"), "order_receipt_date_time", "packed_date_time",
                                    unit="minutes", nonnegative=True, upper_quantile=0.99)

    @chart("Time from order placement to payment (days)", "bar", x="bin_start", y="orders",
           note="All valid delays retained, one-day bins.")
    def payment_delay(self):
        return calc.delay_histogram(self.data("rx_orders"), "date_order_placed", "date_order_paid",
                                    unit="days", binwidth=1)

    @chart("Payment delay by product", "range", x="sku", y="median_days", y2="p90_days",
           note="Median and 90th percentile, negative delays excluded.")
    def payment_delay_by_sku(self):
        return calc.payment_delay_summary(self.data("rx_orders"), group="sku")

    @chart("Payment delay by birth-control flag", "range", x="bc_prescribed", y="median_days", y2="p90_days")
    def payment_delay_by_bc(self):
        return calc.payment_delay_summary(self.data("rx_orders"), group="bc_prescribed")

    @chart("Payment delay by order month", "line", x="month", y="value", color="statistic",
           filters=("statistic",), note="Median and 90th percentile of days from placement to payment.")
    def payment_delay_trend(self):
        d = calc.monthly_delay_summary(self.data("rx_orders"), "date_order_placed", "date_order_paid", "days")
        return d.melt(id_vars=["month", "n_analyzed"], value_vars=["median", "p90"],
                      var_name="statistic", value_name="value")

    @chart("Packing delay by order-receipt month", "line", x="month", y="value", color="statistic",
           filters=("statistic",), note="Median and 90th percentile, in minutes.")
    def packing_delay_trend(self):
        d = calc.monthly_delay_summary(self.data("rx_packed"), "order_receipt_date_time", "packed_date_time",
                                       "minutes")
        return d.melt(id_vars=["month", "n_analyzed"], value_vars=["median", "p90"],
                      var_name="statistic", value_name="value")

    # ---- shipping -------------------------------------------------------------------------------------------
    @chart("Shipments by state", "map", x="state", y="shipments",
           note="US states only; unrecognized or blank states are listed separately.")
    def shipments_by_state(self):
        return calc.shipment_state_counts(self.data("rx_shipments"))

    # ---- internal data quality ----------------------------------------------------------------------------------
    @chart("Missing values per column in orders", "table", internal=True)
    def missing_values(self):
        return calc.missing_summary(self.data("rx_orders"))

    @chart("Order-to-shipment link checks", "table", internal=True)
    def order_shipment_links(self):
        return calc.check_order_shipment_links(self.data("rx_orders"), self.data("rx_shipments"))

    @chart("Order-to-packing (cost) link checks", "table", internal=True)
    def cost_links(self):
        return calc.check_cost_links(self.data("rx_orders"), self.data("rx_packed"), self.data("rx_matches"))

    @classmethod
    def demo_sources(cls, cfg):
        """Synthetic orders, prescriptions, shipments and packing records (seeded)."""
        rng = np.random.default_rng(3)
        n = 900
        placed = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 600, n), unit="D")
        paid = placed + pd.to_timedelta(rng.gamma(1.5, 1.2, n).round(), unit="D")
        sku = rng.choice(["AD-BC-DAYSEE00", "AD-BC-JUNE20FE", "AD-BC-SLYND000", "AD-BC-XULANE00", "AD-CM-OTHER01"],
                         n, p=[.35, .25, .15, .15, .10])
        bc = np.where(np.char.startswith(sku.astype(str), "AD-BC"), "True", "False")
        orders = pd.DataFrame({
            "id": np.arange(1, n + 1), "customer_id": [f"rx-{int(i):04d}" for i in rng.integers(0, 600, n)],
            "date_order_placed": placed, "date_order_paid": paid, "sku": sku, "bc_prescribed": bc,
            "quantity": rng.choice([1, 3, 6, 13], n, p=[.15, .2, .3, .35]) * 28,
            "refills_allowed": rng.choice([0, 1, 3, 5, 11], n, p=[.1, .1, .2, .2, .4]),
            "status": rng.choice(["processed", "archived", "pending", ""], n, p=[.6, .25, .1, .05]),
            "customer_approved": rng.choice(["True", "False", ""], n, p=[.85, .1, .05]),
            "adyn_approved": rng.choice(["True", "False", ""], n, p=[.8, .1, .1]),
            "suspended": rng.choice(["True", "False"], n, p=[.04, .96])})
        pat = rng.integers(0, 500, 1100)
        written = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 600, 1100), unit="D")
        dob = {int(p): pd.Timestamp("1980-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 22))) for p in range(500)}
        rx_written = pd.DataFrame({
            "patient_id": [f"p-{int(p):04d}" for p in pat], "ndc": rng.choice(["00093-1", "00555-2", "68180-3"], 1100),
            "customer_dob": [dob[int(p)] for p in pat], "rx_written_date_time": written,
            "rx_creation_date_time": written + pd.to_timedelta(rng.gamma(2, 6, 1100), unit="h")})
        rx_shipments = pd.DataFrame({
            "rx_order_id": np.arange(1, n + 1),
            "state": rng.choice(["CA", "TX", "NY", "FL", "NC", "WA", "IL", "OH", "PA", "GA", "ZZ", " "], n)})
        received = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 600, n * 2 // 3), unit="D")
        rx_packed = pd.DataFrame({
            "id": np.arange(1, len(received) + 1), "order_receipt_date_time": received,
            "packed_date_time": received + pd.to_timedelta(rng.gamma(2, 90, len(received)), unit="m")})
        rx_matches = pd.DataFrame({"rx_order_id": np.arange(1, len(received) + 1),
                                   "rx_packed_id": np.arange(1, len(received) + 1)})
        return {"rx_orders": orders, "rx_written": rx_written, "rx_shipments": rx_shipments,
                "rx_packed": rx_packed, "rx_matches": rx_matches}
