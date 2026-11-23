"""Record what the PyTorch quality reference runs on, and stop if torch does not use the CUDA
libraries that it was installed with.

pytorch_reference.sh runs this with the reference's own Python:
pytorch_provenance.py OUTPUT VENV SAMPLES MODEL
"""

import hashlib
import json
import os
import re
import subprocess
import sys

CUDA_LIBRARY = re.compile(r"\S*/lib(?:cublas|cublasLt|cudnn|cudart)\.so[.0-9]*")


def cuda_libraries(maps: str) -> list[str]:
    """Return the CUDA libraries in the text of /proc/<pid>/maps."""
    return sorted(set(CUDA_LIBRARY.findall(maps)))


def foreign(libraries: list[str], venv: str) -> list[str]:
    """Return the libraries that do not come from the virtual environment."""
    return [path for path in libraries if not path.startswith(venv.rstrip("/") + "/")]


def main() -> None:
    out, venv, samples, model = sys.argv[1:]
    import torch
    import transformers

    x = torch.randn(64, 64, device="cuda", dtype=torch.float16)
    (x @ x).sum().item()
    cudnn = torch.backends.cudnn.version()
    with open("/proc/self/maps", encoding="utf-8") as stream:
        libraries = cuda_libraries(stream.read())
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface"), "hub"
    )
    cache = os.path.join(hub, "models--" + model.replace("/", "--"))
    with open(os.path.join(cache, "refs", "main"), encoding="utf-8") as stream:
        revision = stream.read().strip()
    with open(samples, "rb") as stream:
        samples_sha256 = hashlib.sha256(stream.read()).hexdigest()
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=False,
    )
    record = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cudnn": cudnn,
        "transformers": transformers.__version__,
        "cuda_libraries": libraries,
        "gpu": gpu.stdout.strip(),
        "model": model,
        "model_revision": revision,
        "samples": samples,
        "samples_sha256": samples_sha256,
    }
    with open(out, "w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record, indent=2))
    outside = foreign(libraries, venv)
    if not libraries or outside:
        raise SystemExit(f"torch did not load its CUDA libraries from {venv}: {outside or 'none found'}")


if __name__ == "__main__":
    main()
