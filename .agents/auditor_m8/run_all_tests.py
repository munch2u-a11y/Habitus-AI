#!/usr/bin/env python3
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

summary = {
    "total_files": len(test_files),
    "passed_files": 0,
    "failed_files": 0,
    "files": {},
}

print(f"Running regression audit across {len(test_files)} test suites...")
for tf_path_str in test_files:
    tf = Path(tf_path_str)
    rel_path = tf.relative_to(PROJECT_ROOT)
    t0 = time.perf_counter()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-o", "addopts=",
        "-v",
        str(tf),
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    status = "PASSED" if res.returncode == 0 else "FAILED"
    if res.returncode == 0:
        summary["passed_files"] += 1
    else:
        summary["failed_files"] += 1
    
    summary["files"][str(rel_path)] = {
        "status": status,
        "returncode": res.returncode,
        "duration_seconds": round(dt, 2),
        "stdout_tail": res.stdout.strip().splitlines()[-5:] if res.stdout else [],
        "stderr_tail": res.stderr.strip().splitlines()[-5:] if res.stderr else [],
    }
    print(f"[{status}] {rel_path} ({dt:.2f}s, code {res.returncode})")

report_path = PROJECT_ROOT / ".agents" / "auditor_m8" / "full_suite_results.json"
report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("\n" + "="*60)
print(f"AUDIT EXECUTION COMPLETE: {summary['passed_files']}/{summary['total_files']} suites passed, {summary['failed_files']} failed.")
print(f"Detailed JSON results written to {report_path}")
