import matplotlib
import pytest
from matplotlib.figure import Figure

from funnel_pkg import FunnelEDA, FunnelPlots
from funnel_pkg.demo import DemoData

matplotlib.use("Agg")


def test_every_chart_returns_a_figure_with_the_staging_note(eda):
    figs = FunnelPlots(eda).all()
    assert len(figs) == 19
    for name, fig in figs.items():
        assert isinstance(fig, Figure), name
        texts = [t.get_text() for t in fig.texts]
        assert any("Staging data" in t for t in texts), name


def test_charts_say_so_when_there_is_nothing_to_draw():
    d = DemoData(n=60)
    import pandas as pd
    d.replacements_per_customer = pd.DataFrame({"n_rep": [], "customers": []})
    fig = FunnelPlots(FunnelEDA(d)).replacements_per_customer()
    assert any("No data" in t.get_text() for ax in fig.axes for t in ax.texts)


def test_data_note_can_be_changed_or_removed(eda):
    fig = FunnelPlots(eda, data_note="").funnel()
    assert not any("Staging" in t.get_text() for t in fig.texts)


def test_make_plots_writes_charts_and_tables(tmp_path):
    import make_plots
    make_plots.main(["--demo", "--output", str(tmp_path), "--dpi", "40"])
    assert len(list((tmp_path / "charts").glob("*.png"))) == 19
    assert len(list((tmp_path / "tables").glob("*.csv"))) >= 30
