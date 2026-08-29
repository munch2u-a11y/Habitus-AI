import sqlite3
import json

db_path = "/home/nemo/habitus-ai-experiments/experiments/graph_native_live/accelerated_gestation_runs/habitus-1787969878668476910.sqlite"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"=== Tables in {db_path} ===")
for t in sorted(tables):
    count = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t:24s}: {count:6d} rows")

print("\n=== Concepts breakdown ===")
for kind, count in cursor.execute("SELECT kind, count(*) FROM concepts GROUP BY kind").fetchall():
    print(f"  kind={kind:15s}: {count:6d}")

print("\n=== Edges breakdown ===")
for side, count in cursor.execute("SELECT side, count(*) FROM edges GROUP BY side").fetchall():
    print(f"  side={side:15s}: {count:6d}")

print("\n=== Metadata entries ===")
for k, v in cursor.execute("SELECT key, substr(value, 1, 80) FROM metadata").fetchall():
    print(f"  {k:30s}: {v}")

print("\n=== Sample Lexemes (kind='lexeme') ===")
for row in cursor.execute("SELECT concept_id, label, vault_id, length(embedding_json), terms_json FROM concepts WHERE kind='lexeme' LIMIT 5").fetchall():
    emb = json.loads(cursor.execute("SELECT embedding_json FROM concepts WHERE concept_id=?", (row[0],)).fetchone()[0])
    print(f"  concept_id={row[0]}, label={row[1]}, dim={len(emb)}, terms={row[4]}")

print("\n=== Sample Crown Concepts (kind='crown') ===")
for row in cursor.execute("SELECT concept_id, label, vault_id, length(embedding_json), terms_json FROM concepts WHERE kind='crown' LIMIT 5").fetchall():
    emb = json.loads(cursor.execute("SELECT embedding_json FROM concepts WHERE concept_id=?", (row[0],)).fetchone()[0])
    print(f"  concept_id={row[0]}, label={row[1]}, dim={len(emb)}, terms={row[4]}")

print("\n=== Output edges from Crown to Lexemes ===")
for row in cursor.execute("""
    SELECT e.source_id, e.target_id, e.log_strength, c_src.label, c_tgt.label
    FROM edges e
    JOIN concepts c_src ON e.source_id = c_src.concept_id
    JOIN concepts c_tgt ON e.target_id = c_tgt.concept_id
    WHERE e.side = 'output' AND c_tgt.kind = 'lexeme'
    LIMIT 10
""").fetchall():
    print(f"  {row[0]} -> {row[1]} (strength={row[2]:.4f}) [{row[3]} -> {row[4]}]")
