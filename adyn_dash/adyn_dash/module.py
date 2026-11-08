"""The shared interface every analysis module follows.

A module is one class holding one analyst's analyses. Each chart is a method marked with @chart(...),
which returns a tidy aggregate table; the decorator's arguments are the chart spec the dashboard uses to
draw it. The build script finds every marked method, so adding a chart never touches the build.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .config import Config
from .source import DataStore, Source


class PrivacyError(ValueError):
    """A chart table contains a person-level column or is too long to be an aggregate."""


@dataclass(frozen=True)
class Chart:
    """Chart spec. Column names refer to the table the method returns."""
    title: str
    mark: str                          # bar | line | point | range | heatmap | table
    x: Optional[str] = None
    y: Optional[str] = None
    y2: Optional[str] = None           # upper bound for mark="range" (y is the lower bound or midpoint)
    color: Optional[str] = None
    stack: bool = False
    x_order: Tuple[str, ...] = ()
    filters: Tuple[str, ...] = ()      # columns the dashboard offers as filters
    note: str = ""                     # assumptions shown under the chart
    internal: bool = False             # data-quality chart for the team, hidden from the client view
    name: str = ""                     # filled in from the method name

    def as_dict(self) -> dict:
        d = asdict(self)
        d["x_order"], d["filters"] = list(self.x_order), list(self.filters)
        return d


def chart(title: str, mark: str, **spec):
    """Mark a method as a dashboard chart."""
    def wrap(fn):
        fn._chart = Chart(title=title, mark=mark, name=fn.__name__, **spec)
        return fn
    return wrap


class AnalysisModule:
    """Base class. Subclasses set name, title, owner and sources, and add @chart methods."""
    name: str = ""
    title: str = ""
    owner: str = ""
    sources: Tuple[Source, ...] = ()
    assumptions: Tuple[str, ...] = ()

    def __init__(self, store: DataStore, cfg: Config | None = None):
        self.store = store
        self.cfg = cfg or store.cfg
        self._by_name: Dict[str, Source] = {s.name: s for s in self.sources}

    def data(self, source_name: str) -> pd.DataFrame:
        return self.store.get(self._by_name[source_name])

    @classmethod
    def demo_sources(cls, cfg: Config) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError(f"{cls.__name__} has no demo data")

    @classmethod
    def charts(cls) -> List[Chart]:
        found = []
        for attr in dir(cls):
            spec = getattr(getattr(cls, attr, None), "_chart", None)
            if spec is not None:
                found.append(spec)
        return sorted(found, key=lambda c: c.name)

    def run(self, chart_name: str) -> pd.DataFrame:
        """Run one chart's method and check that the result is an aggregate."""
        table = getattr(self, chart_name)()
        if not isinstance(table, pd.DataFrame):
            raise TypeError(f"{self.name}.{chart_name} must return a DataFrame")
        return self.check_private(table, f"{self.name}.{chart_name}")

    def check_private(self, table: pd.DataFrame, label: str) -> pd.DataFrame:
        bad = [c for c in table.columns if str(c).lower() in self.cfg.forbidden_columns]
        if bad:
            raise PrivacyError(f"{label} returns person-level columns: {', '.join(map(str, bad))}")
        if len(table) > self.cfg.max_output_rows:
            raise PrivacyError(f"{label} returns {len(table)} rows (limit {self.cfg.max_output_rows}); "
                               "aggregate it before charting")
        return table
