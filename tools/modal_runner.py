"""Run experiment code on Modal.com cloud GPUs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run_on_modal(code_path: str, gpu: str = "T4", timeout: int = 3600) -> dict:
    """Execute a Python script on Modal with the specified GPU."""
    try:
        import modal
    except ImportError:
        print("ERROR: modal package not installed. Run: uv pip install modal", file=sys.stderr)
        return {"exit_code": 1, "stdout": "", "stderr": "modal not installed"}

    code = Path(code_path).read_text()

    app = modal.App("ai-scientist-experiment")

    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "torch", "numpy", "matplotlib", "seaborn",
            "datasets", "transformers", "scikit-learn",
            "pandas", "tqdm", "pyyaml",
        )
    )

    @app.function(image=image, gpu=gpu, timeout=timeout, serialized=True)
    def execute(script_code: str, timeout_secs: int = 3600) -> dict:
        import subprocess
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as f:
            f.write(script_code)
            script_path = f.name

        os.makedirs("/tmp/figures", exist_ok=True)

        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                timeout=timeout_secs,
                cwd="/tmp",
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Timeout after {timeout_secs}s",
            }

    with app.run():
        result = execute.remote(code, timeout)

    return result


def main():
    parser = argparse.ArgumentParser(description="Run experiment on Modal.com")
    parser.add_argument("code_path", help="Path to Python script to execute")
    parser.add_argument("--gpu", default="T4", help="GPU type: T4, A100, H100, L4 (default: T4)")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--output-log", default=None, help="Write stdout to this file")
    args = parser.parse_args()

    result = run_on_modal(args.code_path, gpu=args.gpu, timeout=args.timeout)

    if result["stdout"]:
        print(result["stdout"])

    if result["stderr"]:
        print(result["stderr"], file=sys.stderr)

    if args.output_log:
        Path(args.output_log).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_log, "w") as f:
            f.write(result["stdout"])
            if result["stderr"]:
                f.write("\n--- STDERR ---\n")
                f.write(result["stderr"])

    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
