#!/usr/bin/env python3
"""Victory Auditor Independent Test Runner.

Executes all pytest test files in tests/ sequentially under strict single-runner
discipline, recording exact pass counts, fail counts, duration, and output logs.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path("/home/nemo/habitus-ai-experiments")
EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "graph_native_live"
env = os.environ.copy()
env["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{EXPERIMENT_ROOT}"

test_files = sorted(glob.glob(str(PROJECT_ROOT / "tests" / "test_*.py")))

results = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "total_suites": len(test_files),
    "passed_suites": 0,
    "failed_suites": 0,
    "total_tests_collected": 0,
    "total_tests_passed": 0,
    "total_tests_failed": 0,
    "total_tests_skipped": 0,
    "total_duration_seconds": 0.0,
    "suites": {},
}

log_file = PROJECT_ROOT / ".agents" / "victory_auditor_m8" / "audit_execution.log"
with open(log_file, "w", encoding="utf-8") as log_f:
    log_f.write(f"=== VICTORY AUDITOR INDEPENDENT TEST EXECUTION ===\n")
    log_f.write(f"Start time: {results['timestamp']}\n")
    log_f.write(f"Total test suites: {len(test_files)}\n\n")

start_all = time.perf_counter()

for tf_str in test_files:
    tf = Path(tf_str)
    rel_name = tf.relative_to(PROJECT_ROOT)
    print(f"Running {rel_name}...", flush=True)

    t0 = time.perf_counter()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "-o", "addopts=",
        str(tf),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    dt = time.perf_counter() - t0

    status = "PASSED" if proc.returncode == 0 else "FAILED"
    if proc.returncode == 0:
        results["passed_suites"] += 1
    else:
        results["failed_suites"] += 1

    # Parse stdout for test counts
    lines = proc.stdout.splitlines()
    summary_line = ""
    for line in reversed(lines):
        if "passed" in line or "failed" in line or "error" in line:
            summary_line = line
            break

    suite_entry = {
        "status": status,
        "returncode": proc.returncode,
        "duration_seconds": round(dt, 2),
        "summary": summary_line.strip(),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    results["suites"][str(rel_name)] = suite_entry

    with open(log_file, "a", encoding="utf-8") as log_f:
        log_f.write(f"[{status}] {rel_name} ({dt:.2f}s, returncode={proc.returncode})\n")
        log_f.write(f"  Summary: {summary_line}\n\n")
        if proc.returncode != 0:
            log_f.write(f"  STDOUT:\n{proc.stdout}\n")
            log_f.write(f"  STDERR:\n{proc.stderr}\n\n")

    print(f"[{status}] {rel_name} ({dt:.2f}s) - {summary_line}", flush=True)

total_dt = time.perf_counter() - start_all
results["total_duration_seconds"] = round(total_dt, 2)

json_out = PROJECT_ROOT / ".agents" / "victory_auditor_m8" / "full_suite_results.json"
json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")

with open(log_file, "a", encoding="utf-8") as log_f:
    log_f.write("=" * 70 + "\n")
    log_f.write(f"AUDIT COMPLETE: {results['passed_suites']}/{results['total_suites']} suites passed in {total_dt:.2f}s\n")

print("\n" + "=" * 70)
print(f"INDEPENDENT AUDIT COMPLETE: {results['passed_suites']}/{results['total_suites']} suites passed in {total_dt:.2f}s")
print(f"Results JSON: {json_out}")
print(f"Log File: {log_file}")
