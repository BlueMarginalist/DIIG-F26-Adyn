"""Save every funnel chart (PNG) and the aggregate tables behind them (CSV).

Examples:
    python make_plots.py --demo                       # synthetic data, no database needed
    python make_plots.py --env-file .env              # live database (read-only), credentials from .env
    python make_plots.py --output output --cohort-start 2023-01-01 --cohort-end 2024-01-01
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from funnel_pkg import Config, Database, FunnelData, FunnelEDA, FunnelPlots  # noqa: E402
from funnel_pkg.demo import DemoData  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="use synthetic data instead of the database")
    p.add_argument("--env-file", help="path to a .env file with ADYN_POSTGRES_* variables")
    p.add_argument("--output", default=None, help="output folder (default: output, or demo_output with --demo)")
    p.add_argument("--cohort-start", default="2023-01-01")
    p.add_argument("--cohort-end", default="2024-01-01")
    p.add_argument("--dpi", type=int, default=150)
    a = p.parse_args(argv)

    out = Path(a.output or ("demo_output" if a.demo else "output"))
    (out / "charts").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)

    cfg = Config()
    db = None
    if a.demo:
        data = DemoData(cfg=cfg)
    else:
        db = Database(env_file=a.env_file)
        data = FunnelData(db, cfg)
    try:
        eda = FunnelEDA(data, cfg)
        tables = eda.tables(a.cohort_start, a.cohort_end)
        for name, table in tables.items():
            table.to_csv(out / "tables" / f"{name}.csv", index=False)
        figs = FunnelPlots(eda).all(a.cohort_start, a.cohort_end)
        for name, fig in figs.items():
            fig.savefig(out / "charts" / f"{name}.png", dpi=a.dpi)
    finally:
        if db is not None:
            db.close()
    print(f"Wrote {len(figs)} charts and {len(tables)} tables to {out.resolve()}")


if __name__ == "__main__":
    main()
