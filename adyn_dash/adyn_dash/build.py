"""Run every registered chart and write the files the dashboard reads.

    python -m adyn_dash.build --demo                      # synthetic data, no database
    python -m adyn_dash.build --env-file .env             # live database (read-only)
    python -m adyn_dash.build --demo --modules virtual_care,funnel --out dashboard/data

Output (under --out):
    manifest.json                    one entry per chart: module, spec, assumptions, row count, status
    <module>/<chart>.json            the chart's table as a list of records
A chart that fails is recorded in the manifest with its error; the others still build.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .database import DemoBackend, PostgresBackend
from .config import Config
from .modules import ALL_MODULES
from .source import DataStore


def _clean_value(v):
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, pd.Period):
        return str(v)
    if isinstance(v, (pd.Interval,)):
        return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def to_records(table: pd.DataFrame) -> list:
    """A table as JSON-safe records (NaN/NaT become null, timestamps become ISO strings)."""
    out = table.copy()
    out.columns = [str(c) for c in out.columns]
    return [{k: _clean_value(v) for k, v in row.items()} for row in out.to_dict("records")]


def build(modules: Optional[Iterable[str]] = None, out: str = "dashboard/data", demo: bool = False,
          env_file: Optional[str] = None, cfg: Optional[Config] = None) -> dict:
    cfg = cfg or Config()
    chosen = [ALL_MODULES[n] for n in (modules or ALL_MODULES)]
    backend = DemoBackend(chosen) if demo else PostgresBackend(cfg, env_file=env_file)
    store = DataStore(backend, cfg)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    try:
        for klass in chosen:
            module = klass(store, cfg)
            for spec in klass.charts():
                entry = {"module": klass.name, "module_title": klass.title, "owner": klass.owner,
                         "id": f"{klass.name}.{spec.name}", "spec": spec.as_dict(),
                         "assumptions": list(klass.assumptions)}
                try:
                    table = module.run(spec.name)
                    path = out_dir / klass.name / f"{spec.name}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(to_records(table), indent=1), encoding="utf-8")
                    entry.update(status="ok", rows=len(table), columns=[str(c) for c in table.columns],
                                 file=f"{klass.name}/{spec.name}.json")
                except Exception as error:  # noqa: BLE001  one failing chart must not stop the build
                    entry.update(status="error", error=f"{type(error).__name__}: {error}"[:300])
                entries.append(entry)
    finally:
        backend.close()
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "demo" if demo else "live", "charts": entries}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="use synthetic data instead of the database")
    p.add_argument("--env-file", help="path to a .env file with ADYN_POSTGRES_* variables")
    p.add_argument("--modules", help="comma-separated module names (default: all)")
    p.add_argument("--out", default="dashboard/data")
    p.add_argument("--as-of", help="date used for ages (default: today)")
    a = p.parse_args(argv)
    cfg = Config(as_of=a.as_of) if a.as_of else Config()
    manifest = build(a.modules.split(",") if a.modules else None, a.out, a.demo, a.env_file, cfg)
    ok = [c for c in manifest["charts"] if c["status"] == "ok"]
    bad = [c for c in manifest["charts"] if c["status"] != "ok"]
    print(f"Built {len(ok)} charts into {Path(a.out).resolve()}")
    for c in bad:
        print(f"  FAILED {c['id']}: {c['error']}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
