"""Charts. Every function takes DataFrames and returns a matplotlib Figure.

Figures are built without pyplot, so nothing is shown until you display the
returned figure (a notebook shows it when it's the last line of a cell; a
dashboard can pass it to e.g. st.pyplot(fig) or fig.savefig(...)).
"""
import textwrap
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

BLUE, INK, MUTED, LIGHT = "#2a78d6", "#0b0b0b", "#52514e", "#c3c2b7"
STYLE = {
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlesize": 11, "axes.titlecolor": INK,
}

def type_label(method_type, width=18):
    """'combined pill' -> 'combined pill\n(Daysee, Junel Fe, ...)' using clean.PRODUCTS."""
    from .clean import PRODUCTS
    names = [name for name, t in PRODUCTS.values() if t == method_type]
    if not names:
        return str(method_type)
    return method_type + "\n" + textwrap.fill("(" + ", ".join(names) + ")", width)

def _figure(nrows=1, ncols=1, figsize=(8, 4.5), **kw):
    import matplotlib as mpl
    with mpl.rc_context(STYLE):
        fig = Figure(figsize=figsize, layout="constrained")
        axes = fig.subplots(nrows, ncols, **kw)
    return fig, axes


def hormone_histograms(hormones, bins=25):
    """Histogram of each hormone's values (one panel per hormone)."""
    names = sorted(hormones["hormone"].unique())
    fig, axes = _figure(2, int(np.ceil(len(names) / 2)), figsize=(12, 6))
    for ax, name in zip(axes.flat, names):
        ax.hist(hormones.loc[hormones["hormone"] == name, "value"], bins=bins,
                color=BLUE, edgecolor="white", linewidth=1)
        ax.set_title(name)
        ax.set_ylabel("results")
    fig.suptitle("Hormone distributions", color=INK)
    return fig


def patients_per_product(products):
    """Horizontal bars from analysis.products_summary()."""
    d = products.sort_values("patients")
    fig, ax = _figure(figsize=(8, 4.5))
    labels = d["product"] + "  (" + d["method_type"] + ")"
    ax.barh(labels, d["patients"], color=BLUE, height=0.6)
    for y, v in enumerate(d["patients"]):
        ax.text(v + 0.3, y, str(v), va="center", color=MUTED, fontsize=9)
    ax.set_xlabel("patients")
    ax.set_title("Patients per birth control product", loc="left")
    return fig


def rate_by_thirds_chart(rates, title="Share of patients with any prescription"):
    """Small multiples from analysis.rate_by_thirds(): one panel per variable."""
    variables = list(dict.fromkeys(rates["variable"]))
    fig, axes = _figure(2, int(np.ceil(len(variables) / 2)), figsize=(12, 6), sharey=True)
    top = rates["share"].max() * 1.35
    for ax, var in zip(axes.flat, variables):
        d = rates[rates["variable"] == var]
        ax.bar(d["third"].astype(str), d["share"], color=BLUE, width=0.6)
        for x, (s, n) in enumerate(zip(d["share"], d["n_yes"])):
            ax.text(x, s + top * 0.02, f"{s:.0%}\n(n={n})", ha="center", color=MUTED, fontsize=9)
        ax.set_title(var)
        ax.set_ylim(0, top)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    fig.suptitle(f"{title}, by level (thirds)", color=INK)
    return fig


def score_by_outcome(patients, score="dep_zscore", outcome="any_rx",
                     labels=("no prescription", "tried 1+ prescriptions"), xlabel=None):
    """Stacked histogram of a numeric score, split by a yes/no outcome."""
    d = patients.dropna(subset=[score])
    bins = np.linspace(d[score].min(), d[score].max(), 20)
    fig, ax = _figure(figsize=(8, 4))
    ax.hist([d.loc[~d[outcome].astype(bool), score], d.loc[d[outcome].astype(bool), score]],
            bins=bins, stacked=True, color=[LIGHT, BLUE], edgecolor="white", linewidth=1, label=list(labels))
    ax.set_xlabel(xlabel or score)
    ax.set_ylabel("patients")
    ax.set_title(f"{xlabel or score} by {outcome}", loc="left")
    ax.legend(frameon=False)
    return fig


def spike_timeline(hormones, spikes, freq="MS"):
    """Hormone results per month, with rows equal to the spike value highlighted.

    `spikes` is analysis.spike_summary(hormones).
    """
    is_spike = hormones["value"] == hormones["hormone"].map(spikes["value"])
    month = hormones["created_date"].dt.to_period(freq[0]).dt.to_timestamp()
    counts = hormones.assign(month=month, spike=is_spike).groupby(["month", "spike"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=[False, True], fill_value=0)
    fig, ax = _figure(figsize=(10, 4))
    ax.bar(counts.index, counts[False], width=20, color=LIGHT, label="other results")
    ax.bar(counts.index, counts[True], width=20, bottom=counts[False], color=BLUE, label="spike value")
    ax.set_ylabel("hormone results")
    ax.set_title("Hormone results per month, spike values highlighted", loc="left")
    ax.legend(frameon=False)
    return fig


def funnel(counts, title="North Star"):
    """Horizontal funnel from a Series of step -> count (e.g. analysis.north_star_counts())."""
    d = counts[::-1]
    fig, ax = _figure(figsize=(8, 0.5 * len(d) + 1.5))
    ax.barh(d.index.astype(str), d.values, color=BLUE, height=0.6)
    for y, v in enumerate(d.values):
        ax.text(v, y, f" {v}", va="center", color=MUTED, fontsize=9)
    ax.set_xlabel("patients")
    ax.set_title(title, loc="left")
    return fig


def heatmap(table, title="", xlabel="", ylabel=""):
    """Annotated heatmap of a crosstab (e.g. analysis.switch_matrix())."""
    table = table.rename(index=lambda t: type_label(t, 28), columns=type_label)
    fig, ax = _figure(figsize=(1.6 * table.shape[1] + 3, 0.9 * table.shape[0] + 2.5))
    ax.imshow(table.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(table.shape[1]), table.columns, fontsize=8)
    ax.set_yticks(range(table.shape[0]), table.index)
    hi = table.values.max() or 1
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            v = table.values[i, j]
            ax.text(j, i, v, ha="center", va="center", fontsize=9, color="white" if v > hi / 2 else INK)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    for s in ax.spines.values():
        s.set_visible(False)
    return fig


def by_type_boxplots(patients, variables, type_col="first_type", min_n=3):
    """One panel per variable: its distribution for each product type (box plots)."""
    d = patients.dropna(subset=[type_col])
    counts = d[type_col].value_counts()
    types = [t for t in counts.index if counts[t] >= min_n]
    ncols = min(3, len(variables))
    nrows = int(np.ceil(len(variables) / ncols))
    fig, axes = _figure(nrows, ncols, figsize=(4.2 * ncols, 3.6 * nrows), squeeze=False)
    for ax, v in zip(axes.flat, variables):
        data = [d.loc[d[type_col] == t, v].dropna() for t in types]
        ax.boxplot(data, widths=0.5, patch_artist=True,
                   boxprops=dict(facecolor=BLUE, edgecolor=BLUE, alpha=0.35),
                   medianprops=dict(color=BLUE, linewidth=2), whiskerprops=dict(color=MUTED),
                   capprops=dict(color=MUTED), flierprops=dict(markeredgecolor=MUTED, markersize=3))
        labels = [type_label(t) + f"\nn={counts[t]}" for t in types]
        ax.set_xticks(range(1, len(types) + 1), labels, fontsize=8)
        ax.set_title(v)
    for ax in list(axes.flat)[len(variables):]:
        ax.set_visible(False)
    fig.suptitle(f"Values by {type_col.replace('_', ' ')}", color=INK)
    return fig


def by_type_boxplot(patients, variable, type_col="first_type", min_n=3, ylabel=None):
    """One variable's distribution for each product type, as its own figure."""
    d = patients.dropna(subset=[type_col])
    counts = d[type_col].value_counts()
    types = [t for t in counts.index if counts[t] >= min_n]
    fig, ax = _figure(figsize=(1.9 * len(types) + 2, 5))
    ax.boxplot([d.loc[d[type_col] == t, variable].dropna() for t in types], widths=0.5, patch_artist=True,
               boxprops=dict(facecolor=BLUE, edgecolor=BLUE, alpha=0.35),
               medianprops=dict(color=BLUE, linewidth=2), whiskerprops=dict(color=MUTED),
               capprops=dict(color=MUTED), flierprops=dict(markeredgecolor=MUTED, markersize=3))
    ax.set_xticks(range(1, len(types) + 1), [type_label(t, 22) + f"\nn={counts[t]}" for t in types], fontsize=9)
    ax.set_ylabel(ylabel or variable)
    ax.set_title(f"{variable} by {type_col.replace('_', ' ')}", loc="left")
    return fig