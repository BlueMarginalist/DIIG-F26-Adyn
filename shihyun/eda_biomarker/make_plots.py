"""Save the EDA charts as PNGs in plots/. Can be run from any folder."""
from pathlib import Path

from eda_biomarker_pkg import Database, AdynData, analysis, plots

OUT = Path(__file__).resolve().parent / "plots"
OUT.mkdir(exist_ok=True)

data = AdynData(Database())
vars_ = data.hormone_names + ["dep_zscore"]

figs = {
    "hormone_distribution": plots.hormone_histograms(data.hormones),
    "patients_per_product": plots.patients_per_product(analysis.products_summary(data.rx_orders)),
    "prescription_by_hormone": plots.rate_by_thirds_chart(analysis.rate_by_thirds(data.patients, data.hormone_names)),
    "depression_score_by_rx": plots.score_by_outcome(data.patients, "dep_zscore", xlabel="depression risk z-score"),
    "hormone_spikes": plots.spike_timeline(data.hormones, analysis.spike_summary(data.hormones)),
    "switching": plots.heatmap(analysis.switch_matrix(data.rx_patients), "First vs last method type", "last", "first"),
    "carriers_by_type": plots.heatmap(analysis.type_by_flag(data.patients, "clot_carrier"),
                                      "Clot-variant carriers by first method type", "method type", "carrier"),
}
for v in vars_:
    figs[f"{v}_by_type"] = plots.by_type_boxplot(data.patients, v)
    
for name, fig in figs.items():
    fig.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight")
    print("saved", OUT / f"{name}.png")

# Tables behind the new charts (aggregates only)
#by_type = analysis.compare_by_type(data.patients, vars_)
#print("\npatients per type:", by_type.attrs["n_per_type"])
#print("Bonferroni cutoff:", round(by_type.attrs["bonferroni_cutoff"], 4))
#print(by_type.round(3).to_string())
#print("\nclot carriers vs type, chi-square p:", round(analysis.type_by_flag(data.patients).attrs["p_value"], 3))