"""Exclusive apply_lock behavior (SAFE-03)."""

from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path

from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


class TestApplyLock(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_lock_serializes_and_releases(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            with eng.apply_lock(timeout=2):
                self.assertTrue(Path(eng.LOCK_FILE).exists())
                self.assertTrue(
                    str(Path(eng.LOCK_FILE).resolve()).startswith(
                        str(sandbox.data_dir.resolve())
                    )
                )
            with eng.apply_lock(timeout=2):
                pass  # second acquire succeeds

    def test_lock_contention_times_out(self) -> None:
        with temp_xdg():
            eng = load_engine()
            hold = threading.Event()
            held = threading.Event()
            errors: list[BaseException] = []

            def holder() -> None:
                try:
                    with eng.apply_lock(timeout=30):
                        held.set()
                        hold.wait(timeout=10)
                except BaseException as e:  # noqa: BLE001
                    errors.append(e)

            t = threading.Thread(target=holder, daemon=True)
            t.start()
            self.assertTrue(held.wait(timeout=5), "holder did not acquire lock")
            with self.assertRaises(eng.ApplyError) as ctx:
                with eng.apply_lock(timeout=0.35):
                    pass
            msg = str(ctx.exception).lower()
            self.assertTrue(
                "lock" in msg or "in progress" in msg,
                f"unexpected message: {ctx.exception}",
            )
            hold.set()
            t.join(timeout=5)
            self.assertFalse(errors)
            # After release, acquire works
            with eng.apply_lock(timeout=2):
                pass

    def test_lock_file_path_is_under_data_dir(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            self.assertEqual(
                Path(eng.LOCK_FILE).resolve(),
                (Path(eng.DATA_DIR) / "apply.lock").resolve(),
            )
            self.assertEqual(
                Path(eng.DATA_DIR).resolve(), sandbox.data_dir.resolve()
            )


if __name__ == "__main__":
    unittest.main()
