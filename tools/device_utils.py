"""Device detection and PyTorch backend utilities.

Supports CUDA, MPS (Apple Silicon), and CPU fallback.
"""

from __future__ import annotations

import subprocess
import sys
import json


def detect_device() -> str:
    """Detect the best available PyTorch device.

    Returns one of: "cuda", "mps", "cpu".
    """
    code = (
        "import torch, json; "
        "d = 'cuda' if torch.cuda.is_available() "
        "else ('mps' if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() "
        "else 'cpu'); "
        "print(json.dumps({'device': d, 'version': torch.__version__}))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout.strip())
            return info["device"]
    except Exception:
        pass
    return "cpu"


def get_device_info() -> dict:
    """Return detailed device information."""
    code = """
import torch, json, platform
info = {
    "device": "cpu",
    "torch_version": torch.__version__,
    "python_version": platform.python_version(),
    "platform": platform.system(),
    "arch": platform.machine(),
}
if torch.cuda.is_available():
    info["device"] = "cuda"
    info["cuda_version"] = torch.version.cuda
    info["gpu_name"] = torch.cuda.get_device_name(0)
    info["gpu_count"] = torch.cuda.device_count()
    info["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_mem / 1e9, 1)
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    info["device"] = "mps"
print(json.dumps(info))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return {"device": "cpu", "torch_version": "unknown", "platform": "unknown"}


def get_device_preamble(device: str | None = None) -> str:
    """Return a Python code preamble that sets up the correct device.

    This snippet should be prepended to every generated experiment script.
    """
    if device is None:
        device = detect_device()

    return f'''import torch
import os

# ── Device setup (auto-detected: {device}) ──
if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")
print(f"Using device: {{DEVICE}}")

# Reproducibility
import random
import numpy as np

SEED = int(os.environ.get("SEED", "42"))
torch.manual_seed(SEED)
if DEVICE.type == "cuda":
    torch.cuda.manual_seed_all(SEED)
np.random.seed(SEED)
random.seed(SEED)
print(f"Random seed: {{SEED}}")
'''


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect PyTorch device")
    parser.add_argument(
        "--info", action="store_true", help="Show detailed device info"
    )
    parser.add_argument(
        "--preamble", action="store_true", help="Print device preamble code"
    )
    args = parser.parse_args()

    if args.info:
        info = get_device_info()
        print(json.dumps(info, indent=2))
    elif args.preamble:
        print(get_device_preamble())
    else:
        print(detect_device())


if __name__ == "__main__":
    main()
