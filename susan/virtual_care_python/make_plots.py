"""Run with --demo first. Live mode reads the local project .Renviron."""
import argparse
from pathlib import Path
from virtual_care_pkg import Database, VirtualCareData, VirtualCareEDA, VirtualCarePlots
from virtual_care_pkg.demo import synthetic_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Use synthetic data, no database")
    parser.add_argument("--env-file", default="../../.Renviron")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    if args.demo:
        appointments, reports = synthetic_data()
    else:
        env_file = (folder / args.env_file).resolve()
        with Database(env_file=env_file) as db:
            data = VirtualCareData(db)
            appointments, reports = data.appointments, data.reports
    eda = VirtualCareEDA(appointments, reports)
    plots = VirtualCarePlots(eda)
    out = Path(args.output) if args.output else folder / ("demo_output" if args.demo else "output")
    out.mkdir(parents=True, exist_ok=True)
    for name in ["visit_frequency", "visit_spans", "visit_gaps", "report_waits",
                 "transitions", "video_to_async", "satisfaction", "monthly_visits"]:
        fig = getattr(plots, name)()
        if args.demo:
            fig.suptitle("SYNTHETIC DEMO: " + fig._suptitle.get_text(), fontsize=14)
        fig.savefig(out / f"{name}.png", dpi=160, bbox_inches="tight")
    # Only aggregate tables are exported. Row-level methods remain in memory.
    tables = {
        "visit_summary": eda.visit_summary(), "gap_summary": eda.gap_summary(),
        "report_summary": eda.report_summary(), "report_types": eda.report_type_summary(),
        "report_wait_counts": eda.report_wait_counts(), "transitions": eda.transition_table(),
        "async_summary": eda.async_summary(), "satisfaction": eda.satisfaction_availability(),
        "monthly_visits": eda.monthly_visits(), "quality_summary": eda.quality_summary(),
    }
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=table.index.name is not None)
    print(f"Saved eight graphs and aggregate tables to {out}")
    print("Synthetic example only." if args.demo else "Staging exploration; definitions remain provisional.")


if __name__ == "__main__":
    main()
