"""SECU-01: mutation locking is package-only (fcntl apply_lock).

Shell flock hard-fail was required while shell mutation paths existed.
After Phase 4, GUI/CLI no longer define acquire_apply_lock; exclusive
mutation uses python/kappicon.lock.apply_lock (covered by test_apply_lock).
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "cli" / "kappicon-cli"
GUI = REPO / "gui" / "kappicon"


class TestNoShellMutationLock(unittest.TestCase):
    def test_entrypoints_have_no_shell_flock_mutation_lock(self) -> None:
        for path in (CLI, GUI):
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn(
                "acquire_apply_lock",
                text,
                msg=f"{path.name} still defines/uses shell apply lock",
            )
            # Shell flock-based exclusive apply should not remain
            self.assertNotIn("flock -w", text, msg=f"{path.name} still uses flock -w")

    def test_cli_uses_package_apply_lock(self) -> None:
        text = CLI.read_text(encoding="utf-8", errors="replace")
        self.assertIn("apply_lock", text)
        self.assertIn("from kappicon import", text)


if __name__ == "__main__":
    unittest.main()
