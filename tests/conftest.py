import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def demo():
    from funnel_pkg.demo import DemoData
    return DemoData(n=400, seed=3)


@pytest.fixture()
def eda(demo):
    from funnel_pkg import FunnelEDA
    return FunnelEDA(demo)
