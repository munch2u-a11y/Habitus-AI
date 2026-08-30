import os
import subprocess
import sys
import time

test_files = [
    "tests/test_accelerated_gestation.py",
    "tests/test_adversarial_cognitive_bounds.py",
    "tests/test_app.py",
    "tests/test_audio.py",
    "tests/test_challenger_m1_2.py",
    "tests/test_challenger_m2_1.py",
    "tests/test_challenger_m3_1.py",
    "tests/test_challenger_m3_2.py",
    "tests/test_challenger_m5_1.py",
    "tests/test_challenger_m5_2.py",
    "tests/test_challenger_m6_1.py",
    "tests/test_challenger_m6_2.py",
    "tests/test_challenger_m7_1.py",
    "tests/test_challenger_m7_2.py",
    "tests/test_cognitive_conversability.py",
    "tests/test_gestation_and_agent.py",
    "tests/test_graph_and_learning.py",
    "tests/test_graph_native_live.py",
    "tests/test_m1_adversarial_challenge.py",
    "tests/test_multiresolution_memory.py",
    "tests/test_nursery.py",
    "tests/test_opaque_graph_native.py",
    "tests/test_output_and_demo.py",
    "tests/test_retrieval_pipeline.py",
    "tests/test_reverse_nursery.py",
    "tests/test_store_and_topology.py",
    "tests/test_tools.py",
    "tests/test_user_affinity_gestation.py",
    "tests/test_vector_adapters.py",
]

log_path = ".agents/worker_m8/test_execution.log"
start_total = time.perf_counter()

env = os.environ.copy()
env["PYTHONPATH"] = "src:experiments/graph_native_live"

with open(log_path, "w", encoding="utf-8") as f:
    f.write("============================= COMPREHENSIVE FULL REGRESSION SUITE =============================\n")
    f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    f.write(f"Total Suites: {len(test_files)}\n\n")

passed_suites = 0
failed_suites = 0
suite_results = []

for idx, tf in enumerate(test_files, 1):
    suite_start = time.perf_counter()
    print(f"[{idx}/{len(test_files)}] Running {tf} ...", flush=True)
    cmd = ["python3", "-m", "pytest", "-v", "-o", "addopts=", tf]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    suite_duration = time.perf_counter() - suite_start
    status_str = "PASSED" if proc.returncode == 0 else "FAILED"
    print(f"[{idx}/{len(test_files)}] {tf} -> {status_str} in {suite_duration:.2f}s", flush=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"--- [{idx}/{len(test_files)}] {tf} ({status_str} in {suite_duration:.2f}s) ---\n")
        f.write(proc.stdout)
        f.write(f"\n--- Suite returncode: {proc.returncode} ---\n\n")

    suite_results.append((tf, status_str, suite_duration, proc.returncode))
    if proc.returncode == 0:
        passed_suites += 1
    else:
        failed_suites += 1

total_duration = time.perf_counter() - start_total
summary_header = f"============================= FINAL REGRESSION SUMMARY: {passed_suites}/{len(test_files)} SUITES PASSED, {failed_suites} FAILED ({total_duration:.2f}s) =============================\n"
print(summary_header, flush=True)

with open(log_path, "a", encoding="utf-8") as f:
    f.write(summary_header)
    for tf, status_str, dur, code in suite_results:
        f.write(f"  - {tf}: {status_str} ({dur:.2f}s)\n")
    f.write(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")

sys.exit(0 if failed_suites == 0 else 1)
