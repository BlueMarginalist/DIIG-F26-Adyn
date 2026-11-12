funnel_pkg/          the package
  config.py          every threshold and status name in one frozen dataclass (Config)
  queries.py         SQL only (named %(params)s, no credentials, no names or emails)
  data.py            FunnelData: cached query results, refresh() to re-query
  clean.py           DataFrame in, DataFrame out (types, bulk-account split, groups)
  analysis.py        FunnelEDA: returns tables
  plots.py           FunnelPlots: returns matplotlib Figures
  demo.py            DemoData: synthetic stand-in for FunnelData (no database needed)
make_plots.py        saves every chart (PNG) and its table (CSV)
tests/               pytest (unit tests run anywhere; Postgres tests are opt-in)
pyproject.toml
