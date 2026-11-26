"""Named SQL datasets and the cache that runs each one once."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .config import Config


class SourceUnavailable(RuntimeError):
    """A known data absence that the build can render as an empty state."""
    def __init__(self, key, reason):
        self.key, self.reason = key, reason
        super().__init__(f"{key}: {reason}")


@dataclass(frozen=True)
class Source:
    """One dataset: a .sql file plus the columns the analyses need from it.

    The query lives in sources/<module>/<name>.sql. A client whose tables differ can point
    Config.sql_override_dir at a folder with replacement files of the same names; the declared
    columns are the contract any replacement query has to return.
    """
    module: str
    name: str
    columns: Tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.module}.{self.name}"

    def sql(self, cfg: Config) -> str:
        if cfg.sql_override_dir:
            path = Path(cfg.sql_override_dir) / self.module / f"{self.name}.sql"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return (cfg.sql_dir / self.module / f"{self.name}.sql").read_text(encoding="utf-8")

    def check(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.columns) - set(frame.columns)
        if missing:
            raise ValueError(f"Source {self.key} is missing columns: {', '.join(sorted(missing))}")
        return frame


class DataStore:
    """Fetches each Source once from a backend and keeps the result. refresh() forgets everything."""

    def __init__(self, backend, cfg: Config | None = None):
        self.backend = backend
        self.cfg = cfg or Config()
        self._cache: Dict[str, pd.DataFrame] = {}
        self._unavailable = {}

    def get(self, source: Source) -> pd.DataFrame:
        if source.key in self._unavailable:
            raise self._unavailable[source.key]
        if source.key not in self._cache:
            try:
                frame = source.check(self.backend.fetch(source, self.cfg))
                if frame.empty:
                    raise SourceUnavailable(source.key, "empty_source")
                self._cache[source.key] = frame
            except SourceUnavailable as error:
                self._unavailable[source.key] = error
                raise
        return self._cache[source.key]

    def refresh(self) -> None:
        self._cache.clear()
        self._unavailable.clear()
