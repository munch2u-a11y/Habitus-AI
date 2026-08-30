import os
import sys
import io
import pytest

# Ensure path
sys.path.insert(0, "src")
sys.path.insert(0, "experiments/graph_native_live")

# Redirect stdout and stderr
old_stdout = sys.stdout
old_stderr = sys.stderr
buf = io.StringIO()
sys.stdout = buf
sys.stderr = buf

exit_code = pytest.main([
    "-v",
    "--tb=short",
    "tests/test_adversarial_cognitive_bounds.py",
])

sys.stdout = old_stdout
sys.stderr = old_stderr

output = buf.getvalue()
with open("/home/nemo/habitus-ai-experiments/.agents/reviewer_m7_1/test_output.txt", "w") as f:
    f.write(output)
    f.write(f"\nPYTEST_EXIT_CODE: {exit_code}\n")

print(f"Direct pytest execution completed with exit code: {exit_code}")
