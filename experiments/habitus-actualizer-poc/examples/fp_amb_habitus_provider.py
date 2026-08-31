#!/usr/bin/env python3
"""Official FP-AMB provider adapter for the Habitus memory substrate.

Run this through FP-AMB's own CLI so its scorer and report generators remain
authoritative.  Each run must point at a fresh SQLite database with
``HABITUS_FPAMB_DB``; refusing a non-empty database prevents accidental score
inflation from duplicate ingestion or earlier experiments.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fp_amb import BaseMemoryProvider
from habitus_actualizer._engine.pipeline import BaseAgenticMemoryRAG


class HabitusMemoryProvider(BaseMemoryProvider):
    """Expose Habitus through FP-AMB's two-method provider contract."""

    def __init__(self) -> None:
        database = Path(
            os.environ.get("HABITUS_FPAMB_DB", "/tmp/habitus_fpamb.sqlite")
        ).expanduser()
        database.parent.mkdir(parents=True, exist_ok=True)
        self.mind = BaseAgenticMemoryRAG(
            database,
            direct_top_k=int(os.environ.get("HABITUS_FPAMB_DIRECT_K", "3")),
            lexical_top_k=int(os.environ.get("HABITUS_FPAMB_LEXICAL_K", "3")),
            base_context_chars=int(os.environ.get("HABITUS_FPAMB_CONTEXT_CHARS", "6400")),
            maximum_context_chars=int(
                os.environ.get("HABITUS_FPAMB_CONTEXT_CHARS", "6400")
            ),
        )
        if self.mind.store.list_records():
            self.mind.close()
            raise RuntimeError(
                f"FP-AMB database must begin empty; choose a fresh HABITUS_FPAMB_DB: {database}"
            )
        self.allow_growth = os.environ.get("HABITUS_FPAMB_GROWTH", "1") != "0"
        self.context_chars = int(os.environ.get("HABITUS_FPAMB_CONTEXT_CHARS", "6400"))
        self._turn_index = 0

    @staticmethod
    def _stable_id(prefix: str, material: str) -> str:
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        return f"fpamb:{prefix}:{digest}"

    def ingest_turn(
        self,
        session_id: str,
        timestamp: str,
        speaker: str,
        text: str,
    ) -> None:
        self._turn_index += 1
        material = f"{self._turn_index}\0{session_id}\0{timestamp}\0{speaker}\0{text}"
        # Habitus keeps timestamps and session IDs as structured provenance, but
        # its compact first-person renderer intentionally omits them.  FP-AMB
        # explicitly tests temporal/session reasoning, so retain both in the
        # canonical evidence text made available to the benchmark model.
        evidence = f"During {session_id} at {timestamp}: {text}"
        self.mind.remember(
            evidence,
            source_id=speaker,
            timestamp=timestamp,
            record_id=self._stable_id("record", material),
            event_id=self._stable_id("event", material),
            provenance={
                "benchmark": "FP-AMB",
                "session_id": session_id,
                "timestamp": timestamp,
                "speaker": speaker,
            },
            allow_growth=self.allow_growth,
        )

    def retrieve_context(self, query: str, top_k: int = 5) -> str:
        # FP-AMB's top_k is advisory. Habitus uses independent direct, lexical,
        # and graph-vault lanes, then enforces one shared character budget.
        self.mind.working_memory.entries.clear()
        return self.mind.recall(
            query,
            source_id="FP-AMB evaluator",
            include_current_input=False,
            maximum_context_chars=self.context_chars,
        ).context
