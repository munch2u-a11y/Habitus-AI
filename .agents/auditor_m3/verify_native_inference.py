import os
import subprocess
import json
import tempfile
from pathlib import Path

MODEL_PATH = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
RUNNER_PATH = Path("/home/nemo/habitus-ai-experiments/experiments/graph_native_live/native/graph_soft_generator")
CODEC_PATH = Path("/home/nemo/habitus-ai-experiments/experiments/graph_native_live/native/lexeme_codec")
DATABASE_PATH = Path("/home/nemo/habitus-ai-experiments/experiments/graph_native_live/accelerated_gestation_runs/habitus-1787969878668476910.sqlite")

print("=== Checking File Existence ===")
for name, p in [("Model", MODEL_PATH), ("Runner", RUNNER_PATH), ("Codec", CODEC_PATH), ("Database", DATABASE_PATH)]:
    print(f"  {name:10s}: {p.is_file()} ({p.stat().st_size if p.is_file() else 0} bytes)")

# 1. Test lexeme_codec tokenize and detokenize
print("\n=== Testing lexeme_codec ===")
env = os.environ.copy()
env["OLLAMA_LIB_DIR"] = "/usr/local/lib/ollama"
env["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"

tok_res = subprocess.run([str(CODEC_PATH), str(MODEL_PATH), "tokenize", "hello", "trust"], capture_output=True, text=True, env=env)
print("tokenize returncode:", tok_res.returncode)
tok_json = json.loads(tok_res.stdout)
print("tokenize output dimension:", tok_json["dimension"])
print("tokenize item count:", len(tok_json["items"]))
for item in tok_json["items"]:
    print(f"  word={item['text']!r}, tokens={item['token_ids']}, embedding_len={len(item['embedding'])}")

# 2. Test graph_soft_generator with HABITUS_SOFT_PACKET_V1
print("\n=== Testing graph_soft_generator with HABITUS_SOFT_PACKET_V1 ===")
with tempfile.NamedTemporaryFile("w", suffix=".packet", delete=False) as f:
    f.write("HABITUS_SOFT_PACKET_V1\n")
    f.write("greeting 1.0\n")
    f.write("warm 0.85\n")
    f.write("clear 0.45\n")
    soft_packet = Path(f.name)

try:
    gen_res = subprocess.run(
        [str(RUNNER_PATH), str(MODEL_PATH), str(soft_packet), "32", "42"],
        capture_output=True, text=True, env=env
    )
    print("graph_soft_generator returncode:", gen_res.returncode)
    print("graph_soft_generator stdout:\n", gen_res.stdout)
    if gen_res.stderr:
        print("graph_soft_generator stderr:\n", gen_res.stderr)
finally:
    soft_packet.unlink(missing_ok=True)

# 3. Test graph_soft_generator with HABITUS_OPAQUE_PACKET_V1
print("\n=== Testing graph_soft_generator with HABITUS_OPAQUE_PACKET_V1 ===")
# Generate a test 1024D 2-row packet using token embeddings from tokenize
vec1 = tok_json["items"][0]["embedding"]
vec2 = tok_json["items"][1]["embedding"]
with tempfile.NamedTemporaryFile("w", suffix=".packet", delete=False) as f:
    f.write("HABITUS_OPAQUE_PACKET_V1\n")
    f.write("1024 2\n")
    f.write(" ".join(f"{v:.9g}" for v in vec1) + "\n")
    f.write(" ".join(f"{v:.9g}" for v in vec2) + "\n")
    opaque_packet = Path(f.name)

try:
    env_skip = env.copy()
    env_skip["HABITUS_NATIVE_SKIP_THINK"] = "1"
    gen_res2 = subprocess.run(
        [str(RUNNER_PATH), str(MODEL_PATH), str(opaque_packet), "32", "42"],
        capture_output=True, text=True, env=env_skip
    )
    print("graph_soft_generator (opaque) returncode:", gen_res2.returncode)
    print("graph_soft_generator (opaque) stdout:\n", gen_res2.stdout)
    if gen_res2.stderr:
        print("graph_soft_generator (opaque) stderr:\n", gen_res2.stderr)
finally:
    opaque_packet.unlink(missing_ok=True)
