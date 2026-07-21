"""SECU-01: shell acquire_apply_lock hard-fails when flock is missing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "cli" / "kappicon-cli"
GUI = REPO / "gui" / "kappicon"
CORE_MSG = "flock is required for safe apply (install util-linux)."


def _extract_cli_acquire_apply_lock() -> str:
    text = CLI.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"^acquire_apply_lock\(\) \{.*?\n\}",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not m:
        raise AssertionError("could not extract acquire_apply_lock from cli/kappicon-cli")
    return m.group(0)


class TestShellFlock(unittest.TestCase):
    def test_source_both_files_hard_fail_message(self) -> None:
        for path in (CLI, GUI):
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIn(CORE_MSG, text, msg=f"missing core message in {path}")
            # Must not use the old "if flock then … fi; return 0" skip pattern
            # as the only gate — require explicit hard-fail on missing flock.
            self.assertRegex(
                text,
                r"if ! command -v flock",
                msg=f"{path} should hard-fail when flock missing",
            )

    def test_runtime_missing_flock_fails_closed(self) -> None:
        func = _extract_cli_acquire_apply_lock()
        with tempfile.TemporaryDirectory(prefix="kappicon-flock-") as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            lock_file = data_dir / "apply.lock"
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            # PATH with mkdir only — no flock
            mkdir = shutil.which("mkdir")
            self.assertIsNotNone(mkdir)
            os.symlink(mkdir, bin_dir / "mkdir")

            script = textwrap.dedent(
                f"""\
                #!/bin/bash
                set -e
                DATA_DIR={data_dir!s}
                LOCK_FILE={lock_file!s}
                {func}
                acquire_apply_lock
                """
            )
            script_path = tmp_path / "run.sh"
            script_path.write_text(script, encoding="utf-8")
            bash = shutil.which("bash")
            self.assertIsNotNone(bash)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir)  # no flock; only mkdir
            proc = subprocess.run(
                [bash, str(script_path)],
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            combined = proc.stdout + proc.stderr
            self.assertIn("flock is required for safe apply", combined)

    @unittest.skipUnless(shutil.which("flock"), "flock not installed")
    def test_runtime_with_flock_succeeds(self) -> None:
        func = _extract_cli_acquire_apply_lock()
        with tempfile.TemporaryDirectory(prefix="kappicon-flock-ok-") as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            lock_file = data_dir / "apply.lock"
            script = textwrap.dedent(
                f"""\
                #!/bin/bash
                set -e
                DATA_DIR={data_dir!s}
                LOCK_FILE={lock_file!s}
                {func}
                acquire_apply_lock
                """
            )
            script_path = tmp_path / "run.sh"
            script_path.write_text(script, encoding="utf-8")
            proc = subprocess.run(
                ["bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertTrue(lock_file.exists())


if __name__ == "__main__":
    unittest.main()
