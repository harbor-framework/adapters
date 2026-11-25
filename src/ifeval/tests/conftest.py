from __future__ import annotations

import asyncio
import inspect

import nltk
import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "asyncio: execute async test coroutine in an event loop"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        asyncio.run(pyfuncitem.obj(**testargs))
        return True
    return None


@pytest.fixture(scope="session", autouse=True)
def nltk_tokenizer_data(tmp_path_factory: pytest.TempPathFactory):
    # Reuse tokenizers already on the NLTK search path. Download only what is missing,
    # and remove only the directory this fixture created, even when a download fails.
    missing: list[str] = []
    for package in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{package}")
        except LookupError:
            missing.append(package)

    owned_path: str | None = None
    try:
        if missing:
            data_dir = tmp_path_factory.mktemp("nltk_data")
            owned_path = str(data_dir)
            # Insert before downloading so the finally block owns cleanup on failure.
            nltk.data.path.insert(0, owned_path)
            for package in missing:
                nltk.download(
                    package, download_dir=data_dir, quiet=True, raise_on_error=True
                )
        yield
    finally:
        if owned_path is not None:
            nltk.data.path.remove(owned_path)
