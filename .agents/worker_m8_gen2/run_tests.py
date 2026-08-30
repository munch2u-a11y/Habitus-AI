#!/usr/bin/env python3
import os
import subprocess
import sys

env = os.environ.copy()
env["PYTHONPATH"] = "src:experiments/graph_native_live"

log_file = "/home/nemo/habitus-ai-experiments/.agents/worker_m8_gen2/test_execution.log"

print("Starting pytest full repository suite...")
with open(log_file, "w", encoding="utf-8") as f:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-vv", "-o", "addopts="],
        env=env,
        stdout=f,
        stderr=subprocess.STDOUT,
        cwd="/home/nemo/habitus-ai-experiments",
    )

print(f"Pytest process finished with returncode: {proc.returncode}")
sys.exit(proc.returncode)
