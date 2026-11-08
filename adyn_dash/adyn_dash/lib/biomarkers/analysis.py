"""Summaries and tests. Every function takes DataFrames and returns a DataFrame."""
import pandas as pd
from scipy import stats

from .clean import thirds

"""Per hormone: results, patients, median and share outside the reference range."""
def hormone_summary(hormones):
    g = hormones.groupby("hormone")
    return pd.DataFrame({
        "n_values": g.size(),
        "n_patients": g["customer_id"].nunique(),
        "median": g["value"].median(),
        "share_below": g["below_range"].mean(),
        "share_above": g["above_range"].mean(),
    })

"""Per hormone: how many values are negative or infinite."""
def placeholder_counts(hormones_raw):
    v = hormones_raw["value"]
    return hormones_raw.assign(negative=v < 0, infinite=v == float("inf")) \
        .groupby("hormone")[["negative", "infinite"]].sum()

"""Most repeated value per hormone, how often it appears and when."""
def spike_summary(hormones):
    counts = hormones.groupby(["hormone", "value"]).agg(
        n=("value", "size"), first_seen=("created_date", "min"), last_seen=("created_date", "max"))
    top = counts.sort_values("n", ascending=False).groupby(level="hormone").head(1)
    top = top.reset_index().set_index("hormone").sort_index()
    top["share_of_rows"] = top["n"] / hormones.groupby("hormone").size()
    return top

"""Per sample: how many of its hormones equal that hormone's spike value."""
def spike_samples(hormones):
    spikes = spike_summary(hormones)["value"]
    hit = hormones[hormones["value"] == hormones["hormone"].map(spikes)]
    return hit.groupby(["customer_id", "sample_id"]).agg(
        n_spiked_hormones=("hormone", "size"), created=("created_date", "min")).reset_index()

"""Patients, count and share with `outcome` for each value of `group`.
    `group` can be a column name or a Series aligned to patients (e.g. thirds()).
    """
def rate_by_group(patients, group, outcome="any_rx"):
    key = patients[group] if isinstance(group, str) else group
    g = patients[outcome].astype(float).groupby(key, observed=True)
    return pd.DataFrame({"patients": g.size(), "n_yes": g.sum().astype(int), "share": g.mean()})

"""rate_by_group for each column split into thirds. Long table: column, third, ..."""
def rate_by_thirds(patients, columns, outcome="any_rx"):
    rows = []
    for col in columns:
        t = rate_by_group(patients, thirds(patients[col]), outcome)
        rows.append(t.rename_axis("third").reset_index().assign(variable=col))
    return pd.concat(rows, ignore_index=True)[["variable", "third", "patients", "n_yes", "share"]]

"""Does each hormone relate to (a) any prescription, (b) number tried, (c) first product?
    Mann-Whitney, Spearman and Kruskal-Wallis, with a Bonferroni cutoff.
    """
def hormone_tests(patients, hormones, alpha=0.05):
    rows = []
    for h in hormones:
        d = patients.dropna(subset=[h])
        has, no = d.loc[d["any_rx"], h], d.loc[~d["any_rx"], h]
        rho, p_count = stats.spearmanr(has, d.loc[d["any_rx"], "n_rx_tried"])
        groups = [g[h] for _, g in d.dropna(subset=["first_product"]).groupby("first_product") if len(g) >= 3]
        rows.append({
            "hormone": h, "median_with_rx": has.median(), "median_no_rx": no.median(),
            "p_any_rx": stats.mannwhitneyu(has, no).pvalue,
            "rho_n_tried": rho, "p_n_tried": p_count,
            "p_first_product": stats.kruskal(*groups).pvalue if len(groups) > 1 else float("nan"),
        })
    res = pd.DataFrame(rows).set_index("hormone")
    cutoff = alpha / (3 * len(hormones))
    res["any_significant"] = (res[["p_any_rx", "p_n_tried", "p_first_product"]] < cutoff).any(axis=1)
    res.attrs["bonferroni_cutoff"] = cutoff
    return res

"""Patients and orders per product, with its method type."""
def products_summary(rx_orders):
    return rx_orders.groupby(["product", "method_type"]).agg(
        patients=("customer_id", "nunique"), orders=("sku", "size")
    ).reset_index().sort_values("patients", ascending=False)

"""Counts of first -> last product (or method type) among patients."""
def switch_matrix(rx_patients, by="type"):
    a, b = (f"first_{by}", f"last_{by}") if by == "type" else ("first_product", "last_product")
    return pd.crosstab(rx_patients[a], rx_patients[b])

"""Crosstab of one medical-biography answer against the product patients chose."""
def answer_by_product(answers, rx_patients, field, product_col="first_type"):
    d = answers[[field]].join(rx_patients[[product_col]], how="inner")
    return pd.crosstab(d[field], d[product_col])

"""Per patient: valid DNA sample, valid blood sample, completed medical bio, has a report."""
def north_star(samples, medbio, reports, valid_status="valid", complete_value=None):
    """Per patient: valid DNA sample, valid blood sample, completed medical bio, has a report.

    Sample status 'valid' means usable. On staging `completion` is always empty,
    so by default any medical biography submission counts as complete; pass
    complete_value (e.g. 100) once the team confirms how completion is stored.
    """
    valid = samples[samples["status"] == valid_status]
    report_samples = set(reports["dna_sample_id"].dropna()) | set(reports["hormone_sample_id"].dropna())
    customers = pd.Index(samples["customer_id"].unique()).union(medbio["customer_id"].unique())
    out = pd.DataFrame(index=customers.rename("customer_id"))
    out["valid_dna"] = out.index.isin(valid.loc[valid["kind"] == "KIT-SLV", "customer_id"])
    out["valid_blood"] = out.index.isin(valid.loc[valid["kind"] == "KIT-BLD", "customer_id"])
    done = medbio if complete_value is None else medbio[medbio["completion"] == complete_value]
    # Reports from the newer pipeline (Nov 2023 on) don't link medbio_1_id but
    # carry the questionnaire answers, so a report with answers also counts
    answered = reports[reports["has_answers"].fillna(False).astype(bool)]
    answered_samples = set(answered["dna_sample_id"].dropna()) | set(answered["hormone_sample_id"].dropna())
    via_report = samples.loc[samples["sample_id"].isin(answered_samples), "customer_id"]
    out["medbio_complete"] = out.index.isin(done["customer_id"]) | out.index.isin(via_report)
    out["has_report"] = out.index.isin(samples.loc[samples["sample_id"].isin(report_samples), "customer_id"])
    out["north_star"] = out[["valid_dna", "valid_blood", "medbio_complete"]].all(axis=1)
    out["missing_report"] = out["north_star"] & ~out["has_report"]
    return out

"""Aggregate counts from north_star(), safe to share."""
def north_star_counts(ns):
    return ns[["valid_dna", "valid_blood", "medbio_complete", "north_star", "has_report", "missing_report"]].sum()

def compare_by_type(patients, variables, type_col="first_type", min_n=3, alpha=0.05):
    """Do numeric variables (hormones, dep_zscore) differ across product types?

    One row per variable: median per type, and a Kruskal-Wallis p-value across
    types with at least `min_n` patients. Bonferroni cutoff in .attrs.
    """
    d = patients.dropna(subset=[type_col])
    keep = d[type_col].value_counts()
    d = d[d[type_col].isin(keep[keep >= min_n].index)]
    rows = []
    for v in variables:
        groups = [g[v].dropna() for _, g in d.groupby(type_col)]
        groups = [g for g in groups if len(g) >= min_n]
        row = d.groupby(type_col)[v].median().to_dict()
        row["p_value"] = stats.kruskal(*groups).pvalue if len(groups) > 1 else float("nan")
        rows.append({"variable": v, **row})
    res = pd.DataFrame(rows).set_index("variable")
    res.attrs["n_per_type"] = keep[keep >= min_n].to_dict()
    res.attrs["bonferroni_cutoff"] = alpha / len(variables)
    return res


def type_by_flag(patients, flag="clot_carrier", type_col="first_type"):
    """Crosstab of a yes/no flag against product type, with a chi-square p-value."""
    d = patients.dropna(subset=[flag, type_col])
    table = pd.crosstab(d[flag].astype(bool), d[type_col])
    table.attrs["p_value"] = stats.chi2_contingency(table).pvalue if table.shape[0] > 1 and table.shape[1] > 1 else float("nan")
    return table


def options_by_type(answers, rx_patients, field, type_col="first_type", min_n=5):
    """For each option of a multi-select question: how many picked it, the share of
    each product type among those who did, and a chi-square p-value (picked vs not)."""
    from .clean import split_multiselect

    opts = split_multiselect(answers, field).join(rx_patients[[type_col]], how="inner")
    rows = []
    for opt in opts.columns.drop(type_col):
        picked = opts[opt]
        if picked.sum() < min_n:
            continue
        table = pd.crosstab(picked, opts[type_col])
        p = stats.chi2_contingency(table).pvalue if table.shape == (2, table.shape[1]) and table.shape[1] > 1 else float("nan")
        share = opts[picked][type_col].value_counts(normalize=True)
        rows.append({"option": opt, "n_picked": int(picked.sum()), **share.add_prefix("share_").to_dict(), "p_value": p})
    if not rows:
        return pd.DataFrame()
    res = pd.DataFrame(rows).set_index("option").sort_values("p_value")
    share_cols = [c for c in res.columns if c.startswith("share_")]
    res[share_cols] = res[share_cols].fillna(0)
    return res