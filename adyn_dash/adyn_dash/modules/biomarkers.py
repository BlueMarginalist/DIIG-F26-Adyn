"""Biomarkers and prescriptions. Analyses by Shihyun Kim (shihyun/biomarker-eda branch).

The cleaning and analysis functions live in lib/biomarkers (Shihyun's clean.py and analysis.py,
unchanged). This class replaces her AdynData: it derives the same cached tables from the shared sources,
reshapes each result into a tidy table and attaches the chart spec.
"""
from __future__ import annotations

from functools import cached_property

import numpy as np
import pandas as pd

from ..lib.biomarkers import analysis, clean
from ..module import AnalysisModule, chart
from ..source import Source

ANSWER_KEYS = ("bc_goals", "bc_history", "concerns_about_menstrual_cycle", "experienced_previously",
               "high_trigs", "side_effects_to_avoid", "family_history", "interest_in_conceiving",
               "skip_periods", "smoker")
HORMONES = ("AMH", "DHEA-S", "E2", "FSH", "LH", "SHBG")
METHOD_ORDER = ("combined pill", "progestin-only pill", "injection", "patch", "ring")


def _long_shares(table: pd.DataFrame) -> pd.DataFrame:
    """options_by_type result -> option, method_type, share."""
    if table.empty:
        return pd.DataFrame(columns=["option", "method_type", "share", "n_picked", "p_value"])
    share_cols = [c for c in table.columns if c.startswith("share_")]
    d = table.reset_index().melt(id_vars=["option", "n_picked", "p_value"], value_vars=share_cols,
                                 var_name="method_type", value_name="share")
    d["method_type"] = d["method_type"].str.replace("share_", "", regex=False)
    return d


class Biomarkers(AnalysisModule):
    name = "biomarkers"
    title = "Biomarkers and prescriptions"
    owner = "Shihyun Kim"
    sources = (
        Source("biomarkers", "hormones_raw", ("customer_id", "sample_id", "hormone", "value", "ref_low",
                                              "ref_high", "created_date")),
        Source("biomarkers", "rx_orders", ("customer_id", "sku", "date_order_placed")),
        Source("biomarkers", "genetics", ("customer_id", "dep_zscore", "f5_leiden", "f2_prothrombin")),
        Source("biomarkers", "medbio_answers", ("customer_id",) + ANSWER_KEYS),
        Source("biomarkers", "samples", ("customer_id", "sample_id", "kind", "status")),
        Source("biomarkers", "medbio_submissions", ("customer_id", "completion", "created_date")),
        Source("biomarkers", "reports", ("report_id", "dna_sample_id", "hormone_sample_id", "has_answers")),
    )
    assumptions = (
        "Product names and method types are inferred from SKU codes; confirm with the team.",
        "Negative or infinite hormone values are placeholders and are dropped.",
        "Medical-biography completion is empty on staging, so any submission counts as complete.",
        "Statistical tests use a Bonferroni cutoff; patterns are exploratory, not causal.",
    )

    # ---- derived tables (what AdynData used to cache) -------------------------------------------
    @cached_property
    def hormones(self) -> pd.DataFrame:
        return clean.clean_hormones(self.data("hormones_raw"))

    @cached_property
    def rx_orders(self) -> pd.DataFrame:
        return clean.label_products(self.data("rx_orders"))

    @cached_property
    def rx_patients(self) -> pd.DataFrame:
        return clean.rx_per_patient(self.rx_orders)

    @cached_property
    def genetics(self) -> pd.DataFrame:
        return clean.genetics_flags(self.data("genetics"))

    @cached_property
    def answers(self) -> pd.DataFrame:
        return clean.clean_answers(self.data("medbio_answers").set_index("customer_id"))

    @cached_property
    def patients(self) -> pd.DataFrame:
        return clean.patient_table(clean.hormone_wide(self.hormones), self.rx_patients, self.genetics)

    @property
    def hormone_names(self):
        return sorted(self.hormones["hormone"].unique())

    # ---- prescriptions ----------------------------------------------------------------------------
    @chart("Patients per birth control product", "bar", x="product", y="patients", color="method_type",
           note="Product names are inferred from SKU codes.")
    def products(self):
        return analysis.products_summary(self.rx_orders)

    @chart("First vs last method type", "heatmap", x="last_type", y="first_type", color="patients",
           note="Patients with at least one prescription; off-diagonal cells are patients who switched.")
    def switching(self):
        m = analysis.switch_matrix(self.rx_patients)
        return m.rename_axis(index="first_type", columns="last_type").stack().rename("patients").reset_index()

    # ---- hormones -----------------------------------------------------------------------------------
    @chart("Hormone results outside the reference range", "bar", x="hormone", y="share", color="direction",
           filters=("direction",), note="Share of results below or above the lab reference range.")
    def hormones_out_of_range(self):
        s = analysis.hormone_summary(self.hormones).reset_index()
        return s.melt(id_vars=["hormone", "n_values", "n_patients"], value_vars=["share_below", "share_above"],
                      var_name="direction", value_name="share").assign(
            direction=lambda d: d["direction"].str.replace("share_", "", regex=False))

    @chart("Share of patients with a prescription, by hormone level", "bar", x="variable", y="share",
           color="third", filters=("variable",),
           note="Each hormone is split into thirds (low, middle, high) across patients.")
    def rx_by_hormone_third(self):
        return analysis.rate_by_thirds(self.patients, self.hormone_names)

    @chart("Median hormone level by first method type", "bar", x="variable", y="median", color="method_type",
           filters=("variable",), note="Only method types with at least 3 patients are shown.")
    def hormone_by_type(self):
        variables = self.hormone_names
        res = analysis.compare_by_type(self.patients, variables)
        d = res.drop(columns=["p_value"]).reset_index().melt(id_vars="variable", var_name="method_type",
                                                              value_name="median")
        return d.dropna(subset=["median"])

    # ---- genetics -------------------------------------------------------------------------------------
    @chart("Share of patients with a prescription, by depression-risk score", "bar", x="third", y="share",
           note="Genetic depression-risk z-score split into thirds.")
    def rx_by_depression_third(self):
        return analysis.rate_by_thirds(self.patients, ["dep_zscore"])

    @chart("Clotting-variant carriers by first method type", "heatmap", x="first_type", y="carrier",
           color="patients", note="Carriers have at least one risk allele for Factor V Leiden or Prothrombin.")
    def clot_carriers_by_type(self):
        t = analysis.type_by_flag(self.patients, "clot_carrier")
        return t.rename_axis(index="carrier", columns="first_type").stack().rename("patients").reset_index()

    # ---- medical biography ------------------------------------------------------------------------------
    @chart("Birth control goals and the method chosen", "bar", x="option", y="share", color="method_type",
           stack=True, note="Among patients who picked each goal: share choosing each method type.")
    def bc_goals_by_type(self):
        return _long_shares(analysis.options_by_type(self.answers, self.rx_patients, "bc_goals"))

    @chart("Side effects to avoid and the method chosen", "bar", x="option", y="share", color="method_type",
           stack=True, note="Among patients who picked each side effect: share choosing each method type.")
    def side_effects_by_type(self):
        return _long_shares(analysis.options_by_type(self.answers, self.rx_patients, "side_effects_to_avoid"))

    # ---- North Star -----------------------------------------------------------------------------------------
    @chart("North Star: complete test packages", "bar", x="step", y="patients",
           x_order=("Valid DNA sample", "Valid blood sample", "Medical biography complete",
                    "All three (North Star)", "Has a report", "North Star but no report"),
           note="Valid DNA sample + valid blood sample + completed medical biography.")
    def north_star(self):
        ns = analysis.north_star(self.data("samples"), self.data("medbio_submissions"), self.data("reports"))
        c = analysis.north_star_counts(ns)
        labels = {"valid_dna": "Valid DNA sample", "valid_blood": "Valid blood sample",
                  "medbio_complete": "Medical biography complete", "north_star": "All three (North Star)",
                  "has_report": "Has a report", "missing_report": "North Star but no report"}
        return pd.DataFrame({"step": [labels[k] for k in c.index], "patients": c.to_numpy().astype(int)})

    # ---- internal data quality ----------------------------------------------------------------------------------
    @chart("Statistical tests: hormones vs prescriptions", "table", internal=True,
           note="Mann-Whitney, Spearman and Kruskal-Wallis p-values; compare with the Bonferroni cutoff.")
    def hormone_tests(self):
        return analysis.hormone_tests(self.patients, self.hormone_names).reset_index()

    @chart("Most repeated hormone value (possible placeholder)", "table", internal=True)
    def hormone_spikes(self):
        return analysis.spike_summary(self.hormones).reset_index()

    @chart("Placeholder hormone values dropped", "table", internal=True)
    def placeholder_counts(self):
        return analysis.placeholder_counts(self.data("hormones_raw")).reset_index()

    @classmethod
    def demo_sources(cls, cfg):
        """Synthetic patients, labs, prescriptions, genetics and questionnaire answers (seeded)."""
        rng = np.random.default_rng(5)
        n = 320
        ids = [f"bio-{i:04d}" for i in range(n)]
        skus = list(clean.PRODUCTS)
        base = {"AMH": 2.5, "DHEA-S": 180.0, "E2": 60.0, "FSH": 7.0, "LH": 8.0, "SHBG": 70.0}
        refs = {"AMH": (1.0, 4.0), "DHEA-S": (80.0, 400.0), "E2": (30.0, 400.0), "FSH": (3.0, 10.0),
                "LH": (2.0, 15.0), "SHBG": (20.0, 130.0)}
        h_rows = []
        for i, cid in enumerate(ids):
            sid = f"hs-{i:04d}"
            created = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 600)))
            for h in HORMONES:
                if rng.random() < 0.06:
                    value = base[h] * 0.5  # repeated "spike" value
                elif rng.random() < 0.02:
                    value = -1.0           # placeholder
                else:
                    value = float(base[h] * rng.lognormal(0, 0.45))
                lo, hi = refs[h]
                h_rows.append(dict(customer_id=cid, sample_id=sid, hormone=h, value=value,
                                   ref_low=lo, ref_high=hi, created_date=created))
        rx = []
        for cid in ids:
            if rng.random() < 0.55:
                for k in range(int(rng.integers(1, 4))):
                    rx.append(dict(customer_id=cid, sku=str(rng.choice(skus, p=np.r_[[.3, .2, .1, .1, .08, .07, .05, .04, .03, .03]])),
                                   date_order_placed=pd.Timestamp("2024-02-01") + pd.Timedelta(days=int(rng.integers(0, 500)))))
        genetics = pd.DataFrame({"customer_id": ids, "dep_zscore": rng.normal(0, 1, n),
                                 "f5_leiden": (rng.random(n) < 0.05).astype(int),
                                 "f2_prothrombin": (rng.random(n) < 0.02).astype(int)})
        goals = ["Prevent pregnancy", "Regulate my cycle", "Reduce acne", "Lighter periods"]
        effects = ["Weight gain", "Mood changes", "Low libido", "Nausea"]

        def pick(options):
            k = int(rng.integers(1, 3))
            return str(list(rng.choice(options, size=k, replace=False)))
        answers = pd.DataFrame({"customer_id": ids,
                                **{k: [str(rng.choice(["yes", "no", "sometimes"])) for _ in ids] for k in ANSWER_KEYS}})
        answers["bc_goals"] = [pick(goals) for _ in ids]
        answers["side_effects_to_avoid"] = [pick(effects) for _ in ids]
        answers["bc_history"] = [pick(["Pill", "Patch", "Ring", "None"]) for _ in ids]
        answers["concerns_about_menstrual_cycle"] = [pick(["Heavy", "Irregular", "Painful"]) for _ in ids]
        answers["experienced_previously"] = [pick(["Pill", "Patch", "Ring"]) for _ in ids]
        answers["family_history"] = [pick(["Clots", "Cancer", "None"]) for _ in ids]
        sample_rows, reports = [], []
        for i, cid in enumerate(ids):
            slv, bld = f"slv-{i:04d}", f"bld-{i:04d}"
            sample_rows.append(dict(customer_id=cid, sample_id=slv, kind="KIT-SLV",
                                    status="valid" if rng.random() < 0.9 else "invalid"))
            sample_rows.append(dict(customer_id=cid, sample_id=bld, kind="KIT-BLD",
                                    status="valid" if rng.random() < 0.85 else "invalid"))
            if rng.random() < 0.8:
                reports.append(dict(report_id=i + 1, dna_sample_id=slv, hormone_sample_id=bld,
                                    has_answers=bool(rng.random() < 0.7)))
        submissions = pd.DataFrame({"customer_id": [c for c in ids if rng.random() < 0.8],
                                    "completion": None, "created_date": pd.Timestamp("2024-01-15")})
        return {"hormones_raw": pd.DataFrame(h_rows), "rx_orders": pd.DataFrame(rx), "genetics": genetics,
                "medbio_answers": answers, "samples": pd.DataFrame(sample_rows),
                "medbio_submissions": submissions,
                "reports": pd.DataFrame(reports)[["report_id", "dna_sample_id", "hormone_sample_id", "has_answers"]]}
