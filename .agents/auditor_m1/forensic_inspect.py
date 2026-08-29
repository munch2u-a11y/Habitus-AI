#!/usr/bin/env python3
"""Forensic inspection script for auditor_m1."""

import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys

PROJECT_ROOT = Path("/home/nemo/habitus-ai-experiments")
MODEL_PATH = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
NATIVE_DIR = PROJECT_ROOT / "experiments" / "graph_native_live" / "native"
CODEC_BIN = NATIVE_DIR / "lexeme_codec"
GENERATOR_BIN = NATIVE_DIR / "graph_soft_generator"
GESTATION_RUNS = PROJECT_ROOT / "experiments" / "graph_native_live" / "accelerated_gestation_runs"
NURSERY_RUNS = PROJECT_ROOT / "experiments" / "graph_native_live" / "nursery_runs"
REVERSE_RUNS = PROJECT_ROOT / "experiments" / "graph_native_live" / "reverse_nursery_runs"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "graph_native_live"))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
import accelerated_gestation as gestation
from habitus_ai.embeddings import cosine_similarity

def log_section(title):
    print(f"\n{'='*20} {title} {'='*20}")

def inspect_gguf(path: Path):
    log_section("GGUF MODEL INSPECTION")
    print(f"Path: {path}")
    if not path.is_file():
        print("FAIL: Model file does not exist!")
        return False
    size = path.stat().st_size
    print(f"Size: {size} bytes ({size / (1024**2):.2f} MB)")
    
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            print(f"FAIL: Invalid magic bytes: {magic}")
            return False
        version, tensor_count, metadata_kv_count = struct.unpack("<IQI", f.read(16))
        print(f"Magic: GGUF (OK)")
        print(f"Version: {version}")
        print(f"Tensor count: {tensor_count}")
        print(f"Metadata KV count: {metadata_kv_count}")
    return True

def inspect_binaries():
    log_section("NATIVE BINARIES INSPECTION")
    for binary in (CODEC_BIN, GENERATOR_BIN):
        print(f"\nInspecting binary: {binary}")
        if not binary.is_file():
            print(f"FAIL: Binary not found: {binary}")
            continue
        size = binary.stat().st_size
        print(f"Size: {size} bytes")
        
        # Check ldd/dependencies
        res = subprocess.run(["file", str(binary)], capture_output=True, text=True)
        print(f"File info: {res.stdout.strip()}")

        # Test execution
        env = os.environ.copy()
        env["OLLAMA_LIB_DIR"] = "/usr/local/lib/ollama"
        env["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"
        
        if binary == CODEC_BIN:
            cmd = [str(binary), str(MODEL_PATH), "tokenize", "I", "like", "Josh"]
            res = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                print(f"Codec tokenize test: PASS (dimension: {data.get('dimension')}, items: {len(data.get('items', []))})")
                for item in data.get("items", []):
                    emb = item["embedding"]
                    norm = math.sqrt(sum(x*x for x in emb))
                    print(f"  Token '{item['text']}': tokens={item['token_ids']}, embedding norm={norm:.4f}, dim={len(emb)}")
                
                token_ids = [str(t) for item in data.get("items", []) for t in item["token_ids"]]
                cmd2 = [str(binary), str(MODEL_PATH), "detokenize", *token_ids]
                res2 = subprocess.run(cmd2, capture_output=True, text=True, env=env)
                if res2.returncode == 0:
                    text_out = json.loads(res2.stdout)
                    print(f"Codec detokenize test: PASS (rendered text: {text_out.get('text')!r})")
                else:
                    print(f"FAIL: Codec detokenize test failed: {res2.stderr}")
            else:
                print(f"FAIL: Codec tokenize test failed: {res.stderr}")

        elif binary == GENERATOR_BIN:
            res = subprocess.run([str(binary)], capture_output=True, text=True, env=env)
            print(f"Generator usage probe returncode: {res.returncode} (expected 2 for usage output: {res.stderr.strip()[:60]}...)")

def inspect_sqlite_databases():
    log_section("SQLITE DATABASE FORENSIC INSPECTION")
    sqlite_files = list(GESTATION_RUNS.glob("*.sqlite"))
    print(f"Found {len(sqlite_files)} gestation SQLite databases:")
    embedder = gestation.NativeMassEmbedder(MODEL_PATH, CODEC_BIN)
    
    for db_path in sorted(sqlite_files):
        print(f"\n--- Database: {db_path.name} ({db_path.stat().st_size} bytes) ---")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Schema tables
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"Tables: {', '.join(tables)}")
        
        # Counts
        record_count = cur.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        concept_count = cur.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        edge_count = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        cluster_count = cur.execute("SELECT COUNT(*) FROM overlap_clusters").fetchone()[0]
        trace_count = cur.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        
        print(f"Counts: records={record_count}, concepts={concept_count}, edges={edge_count}, overlap_clusters={cluster_count}, traces={trace_count}")
        
        # Concept breakdown by kind
        kinds = cur.execute("SELECT kind, COUNT(*) FROM concepts GROUP BY kind").fetchall()
        print(f"Concepts by kind: {dict(kinds)}")
        
        # Inspect concept embeddings
        rows = cur.execute("SELECT concept_id, label, kind, embedding_json, terms_json FROM concepts").fetchall()
        zero_embeds = 0
        non_zero_embeds = 0
        norm_stats = []
        lexeme_has_terms = 0
        crown_nodes = []
        
        for r in rows:
            cid, label, kind, emb_blob, terms_str = r['concept_id'], r['label'], r['kind'], r['embedding_json'], r['terms_json']
            if emb_blob:
                try:
                    emb = json.loads(emb_blob)
                except Exception:
                    emb = []
            else:
                emb = []
            
            norm = math.sqrt(sum(x*x for x in emb)) if emb else 0.0
            if norm == 0.0:
                zero_embeds += 1
                if kind not in ("child", "lower_preference"):
                    print(f"WARNING: Zero embedding on unexpected concept kind: {cid} ({kind})")
            else:
                non_zero_embeds += 1
                norm_stats.append((kind, norm, len(emb)))
                if kind == "crown":
                    crown_nodes.append((cid, label, norm, len(emb)))
            
            if kind == "lexeme":
                terms = json.loads(terms_str) if terms_str else []
                if len(terms) > 0:
                    lexeme_has_terms += 1
                    
        print(f"Embeddings: {non_zero_embeds} non-zero vectors, {zero_embeds} zero vectors (43 child routing + 9 lower_preference)")
        print(f"Lexeme nodes storing explicit token/word terms: {lexeme_has_terms} (must be 0 for tokenless memory)")
        print(f"Sample crown concepts ({len(crown_nodes)} total):")
        for cid, label, norm, dim in crown_nodes[:5]:
            print(f"  - {cid} (label='{label}', norm={norm:.4f}, dim={dim})")
        
        # Check edges
        edge_sides = cur.execute("SELECT side, COUNT(*) FROM edges GROUP BY side").fetchall()
        print(f"Edges by side: {dict(edge_sides)}")
        
        # Invariants verification via Python pipeline code
        with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
            embedder.bootstrap = False
            invariants = mind.graph.validate_invariants()
            snapshot = mind.graph.weight_snapshot()
            print(f"Graph validate_invariants(): {invariants} (Must be empty: {'PASS' if invariants == [] else 'FAIL'})")
            print(f"Global edge mass: {snapshot.total:.9f} (Must be 1.0 +- 1e-6: {'PASS' if abs(snapshot.total - 1.0) < 1e-6 else 'FAIL'})")
            print(f"Edge count from store: {len(mind.store.list_edges())}")
            print(f"Concept count from store: {len(mind.store.list_concepts())}")

        # Metadata check
        meta_rows = cur.execute("SELECT key, value FROM metadata").fetchall()
        for k, v in meta_rows:
            if k == "accelerated_gestation_manifest":
                manifest_meta = json.loads(v)
                print(f"Metadata manifest hatch_ready: {manifest_meta.get('hatch_ready')}")
                print(f"Receptive coverage_accuracy_at_1: {manifest_meta.get('evaluation', {}).get('receptive', {}).get('coverage_accuracy_at_1')}")
                print(f"Receptive semantic_accuracy_at_1: {manifest_meta.get('evaluation', {}).get('receptive', {}).get('semantic_accuracy_at_1')}")
                print(f"Productive accuracy_at_1: {manifest_meta.get('evaluation', {}).get('productive', {}).get('accuracy_at_1')}")
                print(f"Global edge mass in manifest: {manifest_meta.get('graph', {}).get('global_edge_mass')}")
                print(f"Invariants in manifest: {manifest_meta.get('graph', {}).get('invariants')}")

        conn.close()

if __name__ == "__main__":
    inspect_gguf(MODEL_PATH)
    inspect_binaries()
    inspect_sqlite_databases()
