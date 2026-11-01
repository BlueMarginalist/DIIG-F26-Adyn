"""Plot methods return matplotlib Figures for notebooks or future dashboards."""
import numpy as np
from matplotlib.figure import Figure
from .clean import VISIT_TYPES, WAIT_GROUPS, SCORE_STATUSES

BLUE = "#3182BD"


class VirtualCarePlots:
    def __init__(self, eda):
        self.eda = eda

    @staticmethod
    def _finish(fig, title, note):
        fig.suptitle(title, fontsize=16)
        fig.text(0.02, 0.015, "Staging data; may include testing records.\n" + note,
                 fontsize=9, va="bottom")
        fig.tight_layout(rect=(0, 0.13, 1, 0.93))
        for ax in fig.axes:
            ax.spines[["top", "right"]].set_visible(False)
        return fig

    def visit_frequency(self):
        data = self.eda.visit_frequency()
        fig = Figure(figsize=(11, 7))
        axes = fig.subplots(2, 2, sharey=True)
        for ax, kind in zip(axes.flat, VISIT_TYPES):
            d = data.loc[data.visit_type.eq(kind)]
            bars = ax.bar(d.visit_group, d.customer_ids, color=BLUE)
            ax.bar_label(bars, labels=[str(n) if n else "" for n in d.customer_ids], padding=3)
            ax.set_title(kind)
            ax.set_ylabel("Customer IDs")
            ax.set_xlabel("Completed visits within this type")
            ax.set_ylim(0, max(1, data.customer_ids.max()) * 1.25)
        return self._finish(fig, "Completed visits per customer",
                            "A customer may appear in more than one panel.")

    def visit_spans(self):
        data = self.eda.visit_counts().dropna(subset=["span_days"])
        fig = Figure(figsize=(10, 5.5))
        ax = fig.subplots()
        rng = np.random.default_rng(1)
        for y, kind in enumerate(VISIT_TYPES):
            values = data.loc[data.visit_type.eq(kind), "span_days"]
            ax.scatter(values, y + rng.uniform(-0.07, 0.07, len(values)),
                       color=BLUE, alpha=0.7)
        ax.set_yticks(range(4), VISIT_TYPES)
        ax.invert_yaxis()
        ax.set_xlabel("Days from first to last completed visit")
        return self._finish(fig, "Time span of recorded completed visits",
                            "Each dot is one customer/type with at least two dated visits.\n"
                            "Blank categories have no eligible spans; vertical offsets separate overlapping dots.")

    def visit_gaps(self):
        data = self.eda.visit_gaps()
        fig = Figure(figsize=(10, 7))
        axes = fig.subplots(2, 1, sharex=True, sharey=True)
        rng = np.random.default_rng(1)
        for ax, col, title in zip(axes, ["first_to_second", "second_to_third"],
                                 ["First to second", "Second to third"]):
            for y, kind in enumerate(VISIT_TYPES):
                values = data.loc[data.visit_type.eq(kind), col].dropna()
                ax.scatter(values, y + rng.uniform(-0.07, 0.07, len(values)),
                           color=BLUE, alpha=0.7)
            ax.set_yticks(range(4), VISIT_TYPES)
            ax.set_title(title)
        axes[0].invert_yaxis()
        axes[-1].set_xlabel("Days between completed visits of the same type")
        return self._finish(fig, "Time between repeat visits",
                            "Each dot is one customer's same-type gap. Groups can contain different customers.\n"
                            "Blank categories have no eligible gaps; vertical offsets separate overlapping dots.")

    def report_waits(self):
        counts = self.eda.report_wait_counts()
        fig = Figure(figsize=(12, 9))
        axes = fig.subplots(3, 2, sharex=True, sharey=True)
        for ax, kind in zip(axes.flat, counts.columns):
            values = counts[kind].to_numpy()
            bars = ax.barh(range(5), values, color=BLUE)
            ax.bar_label(bars, labels=[str(v) if v else "" for v in values], padding=3)
            ax.set_yticks(range(5), WAIT_GROUPS)
            ax.set_title(kind)
            ax.set_xlim(0, max(1, counts.to_numpy().max()) * 1.2)
            ax.set_xlabel("Reports")
        axes[0, 0].invert_yaxis()
        axes.flat[-1].set_visible(False)
        return self._finish(fig, "Report viewing to first later appointment creation",
                            "Appointment creation is a booking-time proxy; all appointment statuses included.\n"
                            "Counts are reports, not patients. Appointments can match multiple reports.\n"
                            "No later booking found refers only to available records; first-time ties use appointment ID.")

    def transitions(self):
        data = self.eda.transition_table()
        fig = Figure(figsize=(9, 7))
        ax = fig.subplots()
        im = ax.imshow(data.to_numpy(), cmap="Blues", vmin=0, vmax=max(1, data.to_numpy().max()))
        ax.set_xticks(range(4), VISIT_TYPES, rotation=20, ha="right")
        ax.set_yticks(range(4), VISIT_TYPES)
        ax.set_xlabel("Next completed visit")
        ax.set_ylabel("Earlier completed visit")
        for i in range(4):
            for j in range(4):
                n = data.iloc[i, j]
                ax.text(j, i, str(n), ha="center", va="center",
                        color="white" if n > data.to_numpy().max()/2 else "black")
        fig.colorbar(im, ax=ax, label="Consecutive visit pairs")
        return self._finish(fig, "Consecutive completed visit types",
                            "Pairs touching tied timestamps are excluded without bridging the excluded records.\n"
                            "Customers may contribute several pairs. Async does not establish refill purpose.")

    def video_to_async(self):
        data = self.eda.video_to_async().sort_values("gap_days")
        fig = Figure(figsize=(10, 6))
        ax = fig.subplots()
        colors = {"15-minute video": BLUE, "25-minute video": "#D55E00"}
        for kind in VISIT_TYPES[:2]:
            mask = data.preceding_video_type.eq(kind)
            if mask.any():
                positions = np.flatnonzero(mask.to_numpy())
                ax.scatter(data.loc[mask, "gap_days"], positions, color=colors[kind], s=55, label=kind)
        ax.set_yticks(range(len(data)), [f"Async visit {i+1}" for i in range(len(data))])
        ax.set_xlabel("Days since the most recent preceding known video")
        if len(data):
            ax.legend(title="Preceding video type")
        else:
            ax.text(0.5, 0.5, "No qualifying video-to-async matches", transform=ax.transAxes, ha="center")
        return self._finish(fig, "Async care after a known video visit",
                            f"{len(data)} async visits across {data.customer_id.nunique()} customer IDs.\n"
                            "Each dot represents one async visit; labels are anonymous display labels.\n"
                            "Refill purpose and yearly care patterns remain unconfirmed. Prior-video ties use ID.")

    def satisfaction(self):
        data = self.eda.satisfaction_availability()
        fig = Figure(figsize=(11, 6))
        ax = fig.subplots()
        left = np.zeros(4)
        colors = [BLUE, "#B8D8D0", "#E69F00", "#D9D9D9"]
        for status, color in zip(SCORE_STATUSES, colors):
            values = data[status].to_numpy()
            if values.sum() == 0:
                continue
            ax.barh(range(4), values, left=left, color=color, label=status)
            for y, value in enumerate(values):
                if value:
                    ax.text(left[y]+value/2, y, str(value), ha="center", va="center")
            left += values
        ax.set_yticks(range(4), VISIT_TYPES)
        ax.invert_yaxis()
        ax.set_xlabel("Completed visits")
        if data.to_numpy().sum():
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2)
        return self._finish(fig, "Satisfaction score availability",
                            "Async blanks are not expected. Recorded means a score exists, not high satisfaction.")

    def monthly_visits(self):
        import pandas as pd
        data = self.eda.monthly_visits()
        fig = Figure(figsize=(11, 7))
        axes = fig.subplots(2, 2, sharex=True, sharey=True)
        for ax, kind in zip(axes.flat, VISIT_TYPES):
            d = data.loc[data.visit_type.eq(kind)]
            ax.bar(pd.to_datetime(d.month), d.visits, width=25, color=BLUE)
            ax.axvline(pd.Timestamp("2024-05-01"), color="#D55E00", linestyle="--")
            ax.set_title(kind)
            ax.set_ylabel("Completed visits")
            ax.tick_params(axis="x", rotation=30)
        return self._finish(fig, "Monthly completed virtual-care visits",
                            "May 2024 marker: client feedback suggests feature-launch testing.\n"
                            "Blank months have no counted qualifying records; source coverage is unconfirmed.")
