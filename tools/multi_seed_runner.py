"""Parallel multi-seed experiment runner with GPU queue management.

Runs the same experiment code with N different random seeds in parallel,
distributing GPUs across workers. Aggregates results using the stats tool.

Used by the experiment skill after a stage completes to validate the best
node's robustness across multiple seeds.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional


# ── GPU management ───────────────────────────────────────────────────────────


def detect_num_gpus() -> int:
    """Detect number of available GPUs via PyTorch or nvidia-smi."""
    # Try torch first
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.device_count()
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return 1  # MPS: treat Apple Silicon as 1 "GPU"
    except Exception:
        pass

    # Fallback: nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if lines:
                return max(1, int(lines[0]))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    return 1  # CPU fallback


class GPUQueue:
    """Manages GPU allocation across parallel workers using a multiprocessing queue."""

    def __init__(self, num_gpus: int):
        self.num_gpus = max(1, num_gpus)
        self.queue: mp.Queue = mp.Queue()
        for gpu_id in range(self.num_gpus):
            self.queue.put(gpu_id)

    def acquire(self, timeout: Optional[float] = None) -> int:
        return self.queue.get(timeout=timeout)

    def release(self, gpu_id: int) -> None:
        self.queue.put(gpu_id)


# ── Worker function (must be picklable, top-level) ───────────────────────────


def _run_seed(args: dict) -> dict:
    """Run a single experiment with a specific seed.

    Runs in a separate process. Sets CUDA_VISIBLE_DEVICES and SEED env vars.
    Returns {"seed": N, "exit_code": int, "stdout": str, "stderr": str, "duration": float, "metrics": dict}
    """
    seed = args["seed"]
    code_path = args["code_path"]
    workdir = args["workdir"]
    log_dir = args["log_dir"]
    gpu_id = args.get("gpu_id")
    timeout = args.get("timeout", 3600)

    env = os.environ.copy()
    env["SEED"] = str(seed)
    if gpu_id is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    log_path = Path(log_dir) / f"seed_{seed}_output.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()
    try:
        result = subprocess.run(
            ["python3", str(code_path)],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + f"\nTimeoutExpired after {timeout}s"
        exit_code = 124

    # Save log
    log_path.write_text(stdout + ("\n--- STDERR ---\n" + stderr if stderr else ""))

    # Parse metrics from stdout
    metrics = _extract_metrics(stdout)

    return {
        "seed": seed,
        "gpu_id": gpu_id,
        "exit_code": exit_code,
        "duration": duration,
        "log_path": str(log_path),
        "metrics": metrics,
    }


def _extract_metrics(text: str) -> dict:
    """Quick-and-dirty metric extraction: lines matching `name: value`."""
    import re
    metrics = {}
    # Match lines like "val_loss: 0.342" or "accuracy: 0.891"
    pattern = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$")
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            name, value = m.group(1), m.group(2)
            try:
                metrics[name] = float(value)
            except ValueError:
                pass
    return metrics


# ── Main runner ──────────────────────────────────────────────────────────────


def run_parallel_seeds(
    code_path: str,
    seeds: list[int],
    workdir: str,
    log_dir: str,
    num_workers: Optional[int] = None,
    num_gpus: Optional[int] = None,
    timeout: int = 3600,
) -> list[dict]:
    """Run the same script with multiple seeds in parallel.

    Args:
        code_path: Python script to execute
        seeds: list of random seed values
        workdir: working directory for subprocess
        log_dir: where to write per-seed logs
        num_workers: max parallel workers (default: min(len(seeds), num_gpus))
        num_gpus: GPU pool size (default: detected)
        timeout: per-seed timeout in seconds

    Returns:
        List of result dicts, one per seed.
    """
    if num_gpus is None:
        num_gpus = detect_num_gpus()
    if num_workers is None:
        num_workers = min(len(seeds), num_gpus)

    gpu_queue = GPUQueue(num_gpus) if num_gpus > 0 else None

    results = []

    # Build task list (GPU assignment done per-task at runtime)
    def _task_with_gpu(seed: int) -> dict:
        gpu_id = gpu_queue.acquire(timeout=300) if gpu_queue else None
        try:
            return _run_seed({
                "seed": seed,
                "code_path": code_path,
                "workdir": workdir,
                "log_dir": log_dir,
                "gpu_id": gpu_id,
                "timeout": timeout,
            })
        finally:
            if gpu_queue and gpu_id is not None:
                gpu_queue.release(gpu_id)

    # Note: using ThreadPoolExecutor instead of ProcessPoolExecutor because
    # the subprocess.run call inside _run_seed is already process-isolated,
    # and ThreadPoolExecutor can share the GPUQueue without pickling issues.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_task_with_gpu, seed): seed for seed in seeds}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                seed = futures[fut]
                results.append({
                    "seed": seed,
                    "exit_code": 1,
                    "error": str(e),
                    "metrics": {},
                })

    results.sort(key=lambda r: r["seed"])
    return results


def aggregate_results(results: list[dict], metric_name: Optional[str] = None) -> dict:
    """Aggregate metric values across seed results using the stats tool."""
    from tools.stats import aggregate_seeds

    values = []
    for r in results:
        m = r.get("metrics", {})
        if metric_name:
            if metric_name in m:
                values.append(float(m[metric_name]))
        else:
            # Use the first numeric metric found
            for _, v in m.items():
                values.append(float(v))
                break

    if not values:
        return {"error": "No metric values found in any seed", "seeds_run": len(results)}

    agg = aggregate_seeds(values)
    agg["seeds_run"] = len(results)
    agg["seeds_successful"] = sum(1 for r in results if r.get("exit_code") == 0)
    return agg


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Parallel multi-seed experiment runner with GPU queue")
    parser.add_argument("code_path", help="Python script to run")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 123, 456],
                        help="Random seeds (default: 42 123 456)")
    parser.add_argument("--workdir", default=".", help="Working directory")
    parser.add_argument("--log-dir", required=True, help="Directory for per-seed logs")
    parser.add_argument("--num-workers", type=int, default=None,
                        help="Max parallel workers (default: min(num_seeds, num_gpus))")
    parser.add_argument("--num-gpus", type=int, default=None,
                        help="GPU pool size (default: auto-detect)")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="Per-seed timeout in seconds")
    parser.add_argument("--metric", default=None,
                        help="Specific metric name to aggregate (default: first found)")
    parser.add_argument("--aggregate", action="store_true",
                        help="Print aggregated statistics instead of per-seed results")
    args = parser.parse_args()

    results = run_parallel_seeds(
        code_path=args.code_path,
        seeds=args.seeds,
        workdir=args.workdir,
        log_dir=args.log_dir,
        num_workers=args.num_workers,
        num_gpus=args.num_gpus,
        timeout=args.timeout,
    )

    if args.aggregate:
        agg = aggregate_results(results, metric_name=args.metric)
        print(json.dumps(agg, indent=2))
    else:
        print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
