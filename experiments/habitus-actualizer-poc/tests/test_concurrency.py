import threading
import time

from habitus_actualizer import Actualizer
from habitus_actualizer.contracts import AbilityId


def test_different_abilities_really_overlap(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    with Actualizer(tmp_path, workers=2) as actualizer:
        original = actualizer.workspace.execute
        barrier = threading.Barrier(2)

        def synchronized(request):
            barrier.wait(timeout=1.0)
            return original(request)

        actualizer.workspace.execute = synchronized
        batch = actualizer.actualize_sync("I'll read `a.txt` and list `.`.")

        assert [item.status for item in batch.receipts] == ["success", "success"]


def test_same_ability_is_fifo(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    with Actualizer(tmp_path, workers=2) as actualizer:
        original = actualizer.workspace.execute
        state_lock = threading.Lock()
        active = 0
        maximum_active = 0

        def observed(request):
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.03)
            try:
                return original(request)
            finally:
                with state_lock:
                    active -= 1

        actualizer.workspace.execute = observed
        batch = actualizer.actualize_sync("I'll read `a.txt` and read `b.txt`.")

        assert all(item.ability_id == AbilityId.READ for item in batch.receipts)
        assert all(item.status == "success" for item in batch.receipts)
        assert maximum_active == 1
