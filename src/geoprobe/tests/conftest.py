from pathlib import Path

import pytest

from geoprobe.sources import load_cases


def pytest_addoption(parser):
    parser.addoption("--data-root", type=Path, help="Pinned local GeoProbe data for integration checks")


@pytest.fixture(scope="session")
def data_root(pytestconfig):
    path = pytestconfig.getoption("--data-root")
    if path is None:
        pytest.skip("Pass --data-root for frozen-dataset integration checks")
    return path.resolve()


@pytest.fixture(scope="session")
def cases(data_root):
    return load_cases(data_root)
