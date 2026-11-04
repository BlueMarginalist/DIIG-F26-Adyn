"""Plot methods return matplotlib Figures for notebooks or future dashboards (built without pyplot)."""
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

BLUE, LIGHT, GREY, RED = "#3182BD", "#9ECAE1", "#B8B8B8", "#C0392B"
STAGING_NOTE = "Staging data; may include testing records."


class FunnelPlots:
    """One method per chart; each reads the matching table from the FunnelEDA, so picture and numbers agree."""

    def __init__(self, eda, data_note=STAGING_NOTE):
        self.eda = eda
        self.data_note = data_note

    # ---- helpers -------------------------------------------------------------------------------------
    def _finish(self, fig, title, note=""):
        fig.suptitle(title, fontsize=14)
        text = (self.data_note + "\n" if self.data_note else "") + note
        fig.text(0.02, 0.015, text.strip(), fontsize=8.5, va="bottom")
        fig.tight_layout(rect=(0, 0.11 if note else 0.07, 1, 0.94))
        for ax in fig.axes:
            ax.spines[["top", "right"]].set_visible(False)
        return fig

    def _empty(self, title):
        fig = Figure(figsize=(7, 3))
        ax = fig.subplots()
        ax.text(0.5, 0.5, "No data to show", ha="center", va="center", color="#666666")
        ax.set_axis_off()
        return self._finish(fig, title)

    @staticmethod
    def _labels(ax, fmt="{:.0f}", horizontal=False):
        for p in ax.patches:
            v = p.get_width() if horizontal else p.get_height()
            if not np.isfinite(v) or v == 0 and not horizontal and False:
                continue
            if horizontal:
                ax.annotate(fmt.format(v), (v, p.get_y() + p.get_height() / 2), xytext=(3, 0),
                            textcoords="offset points", va="center")
            else:
                ax.annotate(fmt.format(v), (p.get_x() + p.get_width() / 2, v), xytext=(0, 3),
                            textcoords="offset points", ha="center")

    def _rate_panel(self, ax, table, value, count, title):
        d = table.copy()
        d["group"] = d["group"].astype(str)
        ax.bar(d["group"], d[value], color=[GREY if s else BLUE for s in d["small_n"]])
        for p, v, n in zip(ax.patches, d[value], d[count]):
            ax.annotate(f"{v:.0f}%\nn={int(n)}", (p.get_x() + p.get_width() / 2, v), xytext=(0, 2),
                        textcoords="offset points", ha="center", fontsize=8)
        ax.set_ylim(0, max(100, float(d[value].max()) * 1.2))
        ax.set_title(title)
        ax.set_ylabel("%")
        ax.tick_params(axis="x", labelrotation=30 if len(d) > 4 else 0, labelsize=8)

    # ---- funnel ----------------------------------------------------------------------------------------
    def funnel(self):
        d = self.eda.funnel()
        d = d[d["stage"] != "Account created"]
        if d.empty:
            return self._empty("Test completion funnel")
        fig = Figure(figsize=(9, 4.5))
        ax = fig.subplots()
        vals = list(d["customers"])[::-1]
        ax.barh(list(d["stage"])[::-1], vals, color=BLUE)
        for p, v, pp in zip(ax.patches, vals, list(d["pct_of_paid"])[::-1]):
            ax.annotate(f"{v:,.0f} ({pp:.0f}%)" if pd.notna(pp) else f"{v:,.0f}",
                        (v, p.get_y() + p.get_height() / 2), xytext=(4, 0), textcoords="offset points", va="center")
        ax.set_xlim(0, (max(vals) or 1) * 1.22)
        ax.set_xlabel("Unique paying customers (percent of paid customers)")
        return self._finish(fig, "Test completion funnel",
                            "Replacement orders and bulk accounts excluded; stages use real status-history dates.")

    def stage_gaps(self):
        d = self.eda.stage_gaps().dropna(subset=["median_days"])
        if d.empty:
            return self._empty("Time between stages")
        fig = Figure(figsize=(9.5, 5))
        ax = fig.subplots()
        labels = [f"{a} -> {b}" for a, b in zip(d["from"], d["to"])][::-1]
        bad = [(x or 0) > 5 for x in list(d["pct_negative"])[::-1]]
        ax.barh(labels, list(d["median_days"])[::-1], color=[GREY if b else BLUE for b in bad])
        self._labels(ax, "{:.1f}", True)
        ax.set_xlabel("Median days")
        return self._finish(fig, "Time between stages",
                            "Grey bars: more than 5% of gaps are negative, so the dates disagree and are unreliable.")

    def ship_rates(self):
        tables = self.eda.ship_rates()
        fig = Figure(figsize=(11, 7))
        axes = fig.subplots(2, 2)
        for ax, (name, t) in zip(axes.flat, tables.items()):
            self._rate_panel(ax, t, "pct_shipped", "paid_customers", f"By {name.replace('_', ' ')}")
        return self._finish(fig, "Paid customers whose kit shipped",
                            "Grey bars: fewer than the small-n threshold of customers.")

    def viewed_rates(self):
        tables = self.eda.result_rates()
        fig = Figure(figsize=(11, 7))
        axes = fig.subplots(2, 2)
        for ax, (name, t) in zip(axes.flat, tables.items()):
            self._rate_panel(ax, t, "pct_viewed", "shipped", f"By {name.replace('_', ' ')}")
        return self._finish(fig, "Shipped customers who viewed a result",
                            "Grey bars: fewer than the small-n threshold of customers.")

    def kit_outcomes(self):
        d = self.eda.kit_outcomes()
        if d.empty:
            return self._empty("Valid samples by kit type")
        fig = Figure(figsize=(7, 4))
        ax = fig.subplots()
        x, w = np.arange(2), 0.35
        for i, (_, row) in enumerate(d.sort_values("is_replacement").iterrows()):
            vals = [100 * row["saliva_valid"] / row["shipments"], 100 * row["blood_valid"] / row["shipments"]]
            ax.bar(x + (i - 0.5) * w, vals, w, color=LIGHT if row["is_replacement"] else BLUE,
                   label=f"Replacement kits (n={int(row['shipments'])})" if row["is_replacement"]
                   else f"Original kits (n={int(row['shipments'])})")
        self._labels(ax, "{:.0f}%")
        ax.set_xticks(x, ["Saliva", "Blood"])
        ax.set_ylim(0, 112)
        ax.set_ylabel("% of shipments with a valid sample")
        ax.legend(frameon=False)
        return self._finish(fig, "Valid samples by kit type",
                            "Every shipment includes one saliva and one blood kit.")

    # ---- replacements ----------------------------------------------------------------------------------------
    def replacements_per_customer(self):
        b = self.eda.replacement_buckets()
        if b["customers"].sum() == 0:
            return self._empty("Replacements per patient")
        fig = Figure(figsize=(7, 4))
        ax = fig.subplots()
        ax.bar(b["bucket"], b["customers"], color=BLUE)
        self._labels(ax)
        ax.set_xlabel("Replacement orders per customer")
        ax.set_ylabel("Customers")
        return self._finish(fig, f"Replacements per patient (n = {int(b['customers'].sum())} patients)")

    def replacement_reasons(self):
        d = self.eda.replacement_reason_classes()
        if d["records"].sum() == 0:
            return self._empty("Replacement reasons")
        fig = Figure(figsize=(8, 3.6))
        ax = fig.subplots()
        d = d.iloc[::-1]
        ax.barh(d["reason_class"], d["records"],
                color=[BLUE if c.startswith("structured") else GREY for c in d["reason_class"]])
        self._labels(ax, horizontal=True)
        ax.set_xlabel(f"Replacement records (n = {int(d['records'].sum())})")
        return self._finish(fig, "Replacement reasons: real vs placeholder text",
                            "Placeholder text (e.g. 'Some reason', 'testing') suggests engineers exercising the flow.")

    def replacements_by_month(self):
        d = self.eda.replacements_by_month().dropna(subset=["paid_month"])
        if d.empty:
            return self._empty("Replacement orders by month paid")
        fig = Figure(figsize=(max(7, 0.5 * len(d) + 3), 4))
        ax = fig.subplots()
        ax.bar([str(m)[:7] for m in d["paid_month"]], d["n"], color=BLUE)
        self._labels(ax)
        ax.tick_params(axis="x", labelrotation=60, labelsize=8)
        return self._finish(fig, "Replacement orders by month paid")

    def replaced_sample_status(self):
        d = self.eda.replaced_sample_status()
        if d.empty:
            return self._empty("Status of the original samples that were replaced")
        fig = Figure(figsize=(8, 4))
        ax = fig.subplots()
        ax.bar([f"{k}\n{s}" for k, s in zip(d["kind"], d["status"])], d["n"],
               color=[BLUE if s == "valid" else RED for s in d["status"]])
        self._labels(ax)
        ax.tick_params(axis="x", labelsize=8)
        return self._finish(fig, "Status of the original samples that were replaced",
                            "KIT-SLV = saliva, KIT-BLD = blood.")

    def replacement_vs_viewing(self):
        d = self.eda.replacement_vs_viewing()
        if d.empty:
            return self._empty("Viewing rate with and without a replacement")
        fig = Figure(figsize=(7, 3.4))
        ax = fig.subplots()
        labels = [f"Needed a replacement\n(n={int(n)})" if r else f"No replacement\n(n={int(n)})"
                  for r, n in zip(d["needed_replacement"], d["shipped_customers"])]
        ax.barh(labels, d["pct_viewed"], color=[BLUE if r else GREY for r in d["needed_replacement"]])
        ax.set_xlim(0, 100)
        self._labels(ax, "{:.0f}%", True)
        ax.set_xlabel("% of shipped customers who viewed a result")
        return self._finish(fig, "Viewing rate with and without a replacement")

    # ---- timing ----------------------------------------------------------------------------------------------------
    def timing_steps(self):
        d = self.eda.timing_steps().dropna(subset=["p50"])
        if d.empty:
            return self._empty("Days between steps")
        fig = Figure(figsize=(3.6 * len(d), 4))
        axes = fig.subplots(1, len(d), squeeze=False)[0]
        for ax, (_, r) in zip(axes, d.iterrows()):
            keys = ["p25", "p50", "p75", "p90"]
            neg = r.get("negative")
            flag = bool(pd.notna(neg) and r["n"] and neg / r["n"] > 0.05)
            ax.bar(keys, [r[k] for k in keys], color=GREY if flag else BLUE)
            self._labels(ax, "{:.1f}")
            ax.set_title(f"{r['step']}\n(n={int(r['n'])}{', dates unreliable' if flag else ''})", fontsize=9)
            ax.set_ylabel("Days")
        return self._finish(fig, "Days between steps",
                            "Grey: more than 5% of gaps are negative (the two dates disagree), so ignore these.")

    # ---- blocking steps ------------------------------------------------------------------------------------------
    def furthest_step(self):
        d = self.eda.furthest_step()
        if d.empty:
            return self._empty("Furthest step reached")
        total = d["orders"].sum()
        vals = list(d["orders"])[::-1]
        fig = Figure(figsize=(9, 4))
        ax = fig.subplots()
        ax.barh([s.split(" ", 1)[1] if s[:1].isdigit() else s for s in d["furthest_step"]][::-1], vals, color=BLUE)
        for p, v in zip(ax.patches, vals):
            ax.annotate(f"{v:,.0f}  ({v / total:.0%})", (v, p.get_y() + p.get_height() / 2), xytext=(3, 0),
                        textcoords="offset points", va="center")
        ax.set_xlim(0, max(vals) * 1.25)
        ax.set_xlabel("Paid orders")
        return self._finish(fig, f"Furthest step reached by each paid order (n = {int(total)})")

    def profile_sequence(self):
        seq, days = self.eda.profile_sequence(), self.eda.profile_days()
        if seq.empty or days.empty or not days.iloc[0]["n"]:
            return self._empty("Profile completion and shipping")
        s, d = seq.iloc[0], days.iloc[0]
        n = int(d["n"])
        buckets = {"Before payment": int(d["profile_before_payment"]),
                   "0-30 days after": n - int(d["profile_before_payment"]) - int(d["over_30_days"]),
                   "30-90 days": int(d["over_30_days"]) - int(d["over_90_days"]),
                   "90+ days": int(d["over_90_days"])}
        fig = Figure(figsize=(11, 4.5))
        a1, a2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1, 1.4]})
        a1.bar(["Profile before\nshipping", "Profile after\nshipping", "No profile\nrecord"],
               [s["profile_before_ship"], s["profile_after_ship"], s["no_profile_record"]], color=[BLUE, RED, GREY])
        self._labels(a1)
        a1.set_title(f"Shipped orders (n={int(s['shipped_orders'])})")
        a2.bar(list(buckets), list(buckets.values()), color=BLUE)
        self._labels(a2)
        a2.set_title(f"Time from payment to complete profile (n={n})")
        return self._finish(fig, "Does profile completion come before shipping?")

    def optional_forms(self):
        d = self.eda.optional_forms()
        if d.empty:
            return self._empty("Optional forms")
        d = d.set_index("shipped")
        fig = Figure(figsize=(7.5, 4))
        ax = fig.subplots()
        x, w = np.arange(2), 0.35
        for i, (shipped, color, label) in enumerate([(True, BLUE, "Shipped"), (False, GREY, "Profile done, not shipped")]):
            if shipped in d.index:
                r = d.loc[shipped]
                ax.bar(x + (i - 0.5) * w, [100 * r["intake_done"] / r["orders"], 100 * r["medhist_done"] / r["orders"]],
                       w, color=color, label=f"{label} (n={int(r['orders'])})")
        self._labels(ax, "{:.0f}%")
        ax.set_xticks(x, ["Intake form", "Medical history"])
        ax.set_ylabel("% completed")
        ax.set_ylim(0, 120)
        ax.legend(frameon=False, loc="upper right")
        return self._finish(fig, "Optional forms: shipped vs stalled orders")

    def steps_by_year(self):
        d = self.eda.steps_by_year()
        d = d[d["paid"] >= 5]
        if d.empty:
            return self._empty("Paid orders reaching each step")
        fig = Figure(figsize=(8.5, 4.5))
        ax = fig.subplots()
        x, w = np.arange(len(d)), 0.26
        for i, (col, label, color) in enumerate([("pct_profile", "Profile complete", LIGHT),
                                                 ("pct_physician", "Physician approved", BLUE),
                                                 ("pct_shipped", "Shipped", RED)]):
            ax.bar(x + (i - 1) * w, d[col], w, label=label, color=color)
        ax.set_xticks(x, [f"{int(y)}\n(n={int(n)})" for y, n in zip(d["yr"], d["paid"])])
        ax.set_ylabel("% of paid orders")
        ax.set_ylim(0, float(d[["pct_profile", "pct_physician", "pct_shipped"]].max().max()) * 1.3)
        ax.legend(frameon=False, loc="upper right", ncol=3)
        return self._finish(fig, "Paid orders reaching each step, by year paid", "Years with fewer than 5 orders omitted.")

    def cohort_by_month(self, start="2023-01-01", end="2024-01-01", burst_factor=2.0):
        d = self.eda.cohort_by_month(start, end)
        if d.empty:
            return self._empty("Paid orders by month")
        burst = [p > burst_factor * float(d["paid"].median()) for p in d["paid"]]
        fig = Figure(figsize=(max(8, 0.7 * len(d) + 3), 4.5))
        ax = fig.subplots()
        x, w = np.arange(len(d)), 0.27
        ax.bar(x - w, d["paid"], w, label="Paid", color=[RED if b else GREY for b in burst])
        ax.bar(x, d["profile_done"], w, label="Profile complete", color=LIGHT)
        ax.bar(x + w, d["shipped"], w, label="Shipped", color=BLUE)
        ax.set_xticks(x, [str(m)[:7] for m in d["paid_month"]], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Orders")
        ax.legend(frameon=False)
        return self._finish(fig, f"Paid orders by month, {start[:7]} to {end[:7]}",
                            f"Red: more than {burst_factor:g}x the median month, which looks like a bulk or test batch.")

    # ---- test accounts and date quality ------------------------------------------------------------------------
    def email_domains(self):
        d = self.eda.email_domains()
        if d.empty:
            return self._empty("Orders by buyer email domain")
        d = d.iloc[::-1]
        other = d["orders"] - d["reserved"] - d["shipped"]
        fig = Figure(figsize=(9, 4))
        ax = fig.subplots()
        ax.barh(d["email_domain"], d["reserved"], color=GREY, label="Reserved (never sent to fulfillment)")
        ax.barh(d["email_domain"], d["shipped"], left=d["reserved"], color=RED, label="Shipped")
        ax.barh(d["email_domain"], other, left=d["reserved"] + d["shipped"], color=LIGHT, label="Other status")
        ax.set_xlabel("Orders")
        ax.legend(frameon=False, loc="lower right")
        return self._finish(fig, "Orders by buyer email domain", "Domains with several buyers only; no addresses shown.")

    def shared_ip_summary(self):
        d = self.eda.shared_ip_summary()
        if d["orders"].sum() == 0:
            return self._empty("Do shared-IP orders look different?")
        fig = Figure(figsize=(7, 3.4))
        ax = fig.subplots()
        ax.barh(d["group"], d["pct_reserved"], color=[GREY, BLUE])
        ax.set_xlim(0, 100)
        self._labels(ax, "{:.0f}%", True)
        ax.set_xlabel("% of orders still reserved (never sent to fulfillment)")
        return self._finish(fig, "Do shared-IP orders look different?")

    def date_quality(self):
        d = self.eda.date_quality()
        if "share_on_busiest_day" not in d or d["share_on_busiest_day"].dropna().empty:
            return self._empty("Date column quality")
        d = d.dropna(subset=["share_on_busiest_day"])
        vals = list(d["share_on_busiest_day"])[::-1]
        fig = Figure(figsize=(9, 4.5))
        ax = fig.subplots()
        ax.barh([f"{t}.{c}" for t, c in zip(d["table_name"], d["column_name"])][::-1], vals,
                color=[RED if v > 20 else BLUE for v in vals])
        self._labels(ax, "{:.0f}%", True)
        ax.set_xlim(0, 110)
        ax.set_xlabel("% of dates on the single busiest day")
        return self._finish(fig, "Date column quality",
                            "Red (over 20%): likely bulk-stamped, do not use for timing.")

    def all(self, cohort_start="2023-01-01", cohort_end="2024-01-01"):
        """{name: Figure} for every chart."""
        names = ["funnel", "stage_gaps", "ship_rates", "viewed_rates", "kit_outcomes", "replacements_per_customer",
                 "replacement_reasons", "replacements_by_month", "replaced_sample_status", "replacement_vs_viewing",
                 "timing_steps", "furthest_step", "profile_sequence", "optional_forms", "steps_by_year",
                 "email_domains", "shared_ip_summary", "date_quality"]
        figs = {n: getattr(self, n)() for n in names}
        figs["cohort_by_month"] = self.cohort_by_month(cohort_start, cohort_end)
        return figs
