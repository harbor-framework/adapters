from __future__ import annotations

import inspect
import io
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, override

import pytest

from contextbench import adapter as adapter_module
from parity.calibration import RETAINED_CORPUS
from tests.helpers import synthetic_digest


@pytest.fixture
def calibration_dir() -> Path:
    """The published parity inputs that `python -m parity.calibrate` fetches.

    Set CONTEXTBENCH_CALIBRATION_DIR to its work directory to run the
    retained-corpus tests; they skip otherwise.
    """
    value = os.environ.get("CONTEXTBENCH_CALIBRATION_DIR", "")
    if not value or not Path(value, "bundle").is_dir():
        pytest.skip("CONTEXTBENCH_CALIBRATION_DIR holds no fetched parity inputs")
    return Path(value).resolve()


@pytest.fixture
def retained_result_dir(calibration_dir: Path) -> Path:
    return calibration_dir / "bundle" / "provenance" / RETAINED_CORPUS


class _SyntheticDigests(dict[str, str]):
    """The pinned digests, and a stand-in digest for every other image."""

    @override
    def __contains__(self, reference: object) -> bool:
        return True

    def __missing__(self, reference: str) -> str:
        return synthetic_digest(reference)


@pytest.fixture(autouse=True, scope="session")
def synthetic_image_digests() -> Iterator[None]:
    """Give the made-up native images of test rows a digest.

    Images in image-digests.json keep their pinned digest. A test that needs an
    image without a digest patches `_image_digests` itself. The fixture spans
    the session so that module fixtures that generate tasks see it.
    """
    digests = _SyntheticDigests(adapter_module._image_digests())
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(adapter_module, "_image_digests", lambda: digests)
        yield


@pytest.fixture
def windows_newlines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Translate newlines in files opened for writing text, as Windows does.

    `Path.write_text` opens files through `io.open`. With `newline=None`, a
    Windows host writes every "\\n" as "\\r\\n".
    """
    real_open: Callable[..., Any] = io.open
    parameters = inspect.signature(real_open)

    def windows_open(*args: Any, **kwargs: Any) -> Any:
        call = parameters.bind(*args, **kwargs)
        call.apply_defaults()
        mode = call.arguments["mode"]
        writes_text = "b" not in mode and bool(set(mode) & set("wax+"))
        if writes_text and call.arguments["newline"] is None:
            call.arguments["newline"] = "\r\n"
        return real_open(*call.args, **call.kwargs)

    monkeypatch.setattr(io, "open", windows_open)
